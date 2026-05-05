"""
apps/bookings/management/commands/mark_overdue.py

Management command — marks past-due installments as overdue.
Run daily via cron: 0 1 * * * docker exec app python manage.py mark_overdue

Condition: due_date < today AND status = 'pending'
Action:    bulk update status = 'overdue'
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Installment


class Command(BaseCommand):
    help = 'Mark all past-due pending installments as overdue.'

    def handle(self, *args, **options):
        today = timezone.localdate()

        updated = (
            Installment.objects
            .filter(
                due_date__lt=today,
                status=Installment.Status.PENDING,
            )
            .update(status=Installment.Status.OVERDUE)
        )

        if updated:
            self.stdout.write(
                self.style.WARNING(f'Marked {updated} installment(s) as overdue.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('No overdue installments found.')
            )