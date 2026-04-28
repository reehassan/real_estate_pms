"""
apps/bookings/signals.py

Signals for the bookings app.
post_save on Booking → auto-generate installments on creation only.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Booking
from .utils import generate_installments


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    if created:
        generate_installments(instance)