"""
apps/bookings/utils.py

Business logic for installment generation.
Call generate_installments(booking) once after a Booking is created.
Never call it twice on the same booking — it will create duplicates.
"""

from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from .models import Booking, Installment


def generate_installments(booking: Booking) -> None:

    PLAN_COUNTS = {
        Booking.PaymentPlan.LUMP_SUM:   1,
        Booking.PaymentPlan.THREE_YEAR: 36,
        Booking.PaymentPlan.FIVE_YEAR:  60,
    }

    count        = PLAN_COUNTS[booking.payment_plan]
    installable  = booking.total_price - booking.down_payment
    amount_per   = (installable / Decimal(count)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    last_amount  = installable - (amount_per * (count - 1))
    project_code = booking.plot.project.name[:3].upper()
    start_date   = booking.booking_date

    installments = []

    for i in range(1, count + 1):

        if count == 1:
            due_date = start_date + relativedelta(days=30)
        else:
            due_date = start_date + relativedelta(months=i)

        challan_number = f'DLD-{project_code}-{booking.pk:04d}-{i:03d}'
        amount         = last_amount if i == count else amount_per

        installments.append(
            Installment(
                booking            = booking,
                installment_number = i,
                challan_number     = challan_number,
                due_date           = due_date,
                amount_due         = amount,
                status             = Installment.Status.PENDING,
            )
        )

    Installment.objects.bulk_create(installments)