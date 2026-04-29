"""
Signals for the bookings app.

Key behaviors:
1) Booking created   -> Plot.status = BOOKED
2) Booking cancelled -> Plot.status = AVAILABLE
3) Installment paid (when all of a booking's installments are paid)
                      -> Booking.status = COMPLETED, Plot.status = SOLD
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Booking, Installment
from .utils import generate_installments
from apps.projects_and_plots.models import Plot


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    if created:
        # Guard: if the booking is created already cancelled, do not reserve
        # the plot (otherwise plot state becomes inconsistent).
        if instance.status == Booking.Status.CANCELLED:
            return

        # When a booking is created, mark the associated plot as booked.
        # Plot.status uses the TextChoices values from Plot.Status.
        if instance.plot.status != Plot.Status.BOOKED:
            instance.plot.status = Plot.Status.BOOKED
            instance.plot.save(update_fields=["status"])
        generate_installments(instance)
    else:
        # When a booking is cancelled, make the plot available again.
        # Guard: once a plot is SOLD, cancelling should not flip it back to AVAILABLE.
        if (
            instance.status == Booking.Status.CANCELLED
            and instance.plot.status != Plot.Status.AVAILABLE
            and instance.plot.status != Plot.Status.SOLD
        ):
            instance.plot.status = Plot.Status.AVAILABLE
            instance.plot.save(update_fields=["status"])


@receiver(post_save, sender=Installment)
def installment_post_save(sender, instance, created, **kwargs):
    """
    When an installment becomes PAID and it's the last remaining unpaid installment
    for the booking, finalize the booking and mark the plot as SOLD.
    """
    if instance.status != Installment.Status.PAID:
        return

    booking = instance.booking

    # Guard against re-processing.
    if booking.status in {Booking.Status.CANCELLED, Booking.Status.COMPLETED}:
        return

    # Fast check before taking locks.
    if booking.installments.exclude(status=Installment.Status.PAID).exists():
        return

    with transaction.atomic():
        booking_locked = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking_locked.status in {Booking.Status.CANCELLED, Booking.Status.COMPLETED}:
            return

        plot = Plot.objects.select_for_update().get(pk=booking_locked.plot_id)

        # Re-check under lock to avoid edge cases during concurrent updates.
        if booking_locked.installments.exclude(status=Installment.Status.PAID).exists():
            return

        booking_locked.status = Booking.Status.COMPLETED
        booking_locked.save(update_fields=["status"])

        if plot.status != Plot.Status.SOLD:
            plot.status = Plot.Status.SOLD
            plot.save(update_fields=["status"])