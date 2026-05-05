"""
apps/bookings/signals.py

Handles all Booking lifecycle → Plot status transitions.

Transition map:
    Booking created (active)        → Plot: available  → booked
    Booking → cancelled             → Plot: booked     → available
    Booking → completed             → Plot: booked     → sold
    Booking → active (re-activated) → Plot: available  → booked

Out of scope:
    - Installment status updates (handled separately)
    - Payment recording
    - Overpayment / refund logic
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.bookings.models import Booking
from apps.bookings.services.installment_service import generate_installments
from apps.projects_and_plots.models import Plot


# ─────────────────────────────────────────────
# PRE-SAVE: capture previous status before DB write
# ─────────────────────────────────────────────

@receiver(pre_save, sender=Booking)
def capture_previous_status(sender, instance, **kwargs):
    """
    Store the previous status on the instance so post_save can diff it.
    New bookings (no pk yet) get _previous_status = None.
    """
    if instance.pk:
        try:
            instance._previous_status = Booking.all_objects.get(pk=instance.pk).status
        except Booking.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


# ─────────────────────────────────────────────
# POST-SAVE: react to status transitions
# ─────────────────────────────────────────────

@receiver(post_save, sender=Booking)
def sync_plot_status_and_generate_installments(sender, instance, created, **kwargs):
    """
    Keeps Plot.status in sync with Booking.status transitions.
    Installments are generated only once, on booking creation.
    """
    prev   = instance._previous_status
    current = instance.status

    if created:
        # Brand-new booking — lock the plot and build the schedule.
        _set_plot_status(instance.plot, Plot.Status.BOOKED)
        generate_installments(instance)
        return

    # No status change — nothing to do (e.g. notes edit, price correction).
    if prev == current:
        return

    if current == Booking.Status.CANCELLED:
        # Booking cancelled — release the plot back to market.
        _set_plot_status(instance.plot, Plot.Status.AVAILABLE)

    elif current == Booking.Status.COMPLETED:
        # Full payment received — ownership transferred.
        _set_plot_status(instance.plot, Plot.Status.SOLD)

    elif current == Booking.Status.ACTIVE and prev == Booking.Status.CANCELLED:
        # Booking re-activated after cancellation — re-lock the plot.
        # Note: re-activating after COMPLETED is intentionally not handled;
        # that would require a separate business decision.
        _set_plot_status(instance.plot, Plot.Status.BOOKED)


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def _set_plot_status(plot, status: str) -> None:
    """Single place to update plot status — easier to mock in tests."""
    if plot.status != status:          # skip DB write if already correct
        plot.status = status
        plot.save(update_fields=['status', 'updated_at'])