from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Installment


class Command(BaseCommand):
    help = "Mark overdue installments (due_date < today and status=pending) as overdue."

    def handle(self, *args, **options):
        today = timezone.localdate()

        with transaction.atomic():
            qs = Installment.objects.filter(
                due_date__lt=today,
                status=Installment.Status.PENDING,
            )
            updated = qs.update(status=Installment.Status.OVERDUE)

        self.stdout.write(self.style.SUCCESS(f"Marked {updated} installments as overdue."))

