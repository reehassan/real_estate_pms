"""
apps/bookings/signals.py

Handles all Booking lifecycle → Plot status transitions.

Transition map:
    Booking created (TOKEN)         → Plot: available  → token
    Booking created (ACTIVE)        → Plot: available  → booked  + generate installments
    Booking TOKEN   → ACTIVE        → Plot: token      → booked  + generate installments
    Booking → CANCELLED             → Plot: token/booked → available
    Booking → COMPLETED             → Plot: booked     → sold
    Booking ACTIVE  → TOKEN         → not allowed (handled by guard, no transition)

Out of scope:
    - Installment status updates (handled by management command)
    - Payment recording
    - Overpayment / refund logic
    - Re-activation after COMPLETED
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.bookings.models import Booking
from apps.bookings.services.installment_service import generate_installments
from apps.projects_and_plots.models import Plot


# ─────────────────────────────────────────────
# PRE-SAVE: capture previous status
# ─────────────────────────────────────────────

@receiver(pre_save, sender=Booking)
def capture_previous_status(sender, instance, **kwargs):
    """
    Store the previous status on the instance so post_save can diff it.
    New bookings (no pk yet) get _previous_status = None.
    """
    if instance.pk:
        try:
            instance._previous_status = (
                Booking.all_objects.get(pk=instance.pk).status
            )
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
    Installment generation happens only on TOKEN → ACTIVE transition
    (or on creation if booking is created directly as ACTIVE).
    """
    prev    = instance._previous_status
    current = instance.status

    if created:
        if current == Booking.Status.TOKEN:
            # Token received — hold the plot at TOKEN stage
            _set_plot_status(instance.plot, Plot.Status.TOKEN)

        elif current == Booking.Status.ACTIVE:
            # Booking created directly as ACTIVE (down payment already collected)
            # Lock the plot and generate the full installment schedule
            _set_plot_status(instance.plot, Plot.Status.BOOKED)
            generate_installments(instance)

        return

    # ── Existing booking — handle status transitions ───────────────

    # No status change — nothing to do (notes edit, price correction etc.)
    if prev == current:
        return

    if current == Booking.Status.ACTIVE and prev == Booking.Status.TOKEN:
        # Down payment collected — formalize the booking
        # Plot moves from TOKEN → BOOKED and schedule is generated
        _set_plot_status(instance.plot, Plot.Status.BOOKED)
        generate_installments(instance)

    elif current == Booking.Status.CANCELLED:
        # Booking cancelled at any stage — release plot back to market
        _set_plot_status(instance.plot, Plot.Status.AVAILABLE)

    elif current == Booking.Status.COMPLETED:
        # All installments paid — ownership transferred
        _set_plot_status(instance.plot, Plot.Status.SOLD)

    elif current == Booking.Status.ACTIVE and prev == Booking.Status.CANCELLED:
        # Re-activated after cancellation — re-lock the plot
        # Note: re-activating after COMPLETED is intentionally not handled
        _set_plot_status(instance.plot, Plot.Status.BOOKED)
        generate_installments(instance)


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def _set_plot_status(plot, status: str) -> None:
    """Single place to update plot status — easier to mock in tests."""
    if plot.status != status:
        plot.status = status
        plot.save(update_fields=['status', 'updated_at'])