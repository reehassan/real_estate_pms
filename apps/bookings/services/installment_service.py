"""
apps/bookings/services/installment_service.py

Installment generation logic.
Called by post_save signal on Booking (created=True only).

Rounding strategy:
    Each installment is floor-rounded to 2 decimal places.
    The last installment absorbs the remainder so that:
        sum(amount_due) == total_price - down_payment  (exactly)
"""

from decimal import Decimal, ROUND_DOWN

from dateutil.relativedelta import relativedelta

from apps.bookings.models import Booking, Installment


# Maps payment plan → number of installments
_PLAN_COUNT: dict[str, int] = {
    Booking.PaymentPlan.LUMP_SUM:   1,
    Booking.PaymentPlan.THREE_YEAR: 36,
    Booking.PaymentPlan.FIVE_YEAR:  60,
}


def generate_installments(booking: Booking) -> list[Installment]:
    """
    Generate and bulk-create the installment schedule for a booking.

    Rules:
        - Down payment is excluded from the schedule.
        - Lump sum → 1 installment due 30 days from booking_date.
        - 3yr / 5yr → monthly installments starting 1 month after booking_date.
        - Remainder from Decimal division is absorbed by the last installment.

    Returns:
        List of created Installment instances.

    Raises:
        ValueError: if remaining amount is zero or negative (fully covered by down payment).
        KeyError: if payment_plan is not a recognised choice.
    """
    remaining: Decimal = booking.total_price - booking.down_payment

    if remaining <= 0:
        # Down payment covers everything — no installment schedule needed.
        return []

    count: int = _PLAN_COUNT[booking.payment_plan]

    # Project code travels through: Booking → Plot → Project
    # Adjust the attribute path if your Project model uses a different field name.
    project_code: str = booking.plot.project.code  

    # Floor-round each unit; last installment gets the remainder.
    unit: Decimal = (remaining / count).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    last_amount: Decimal = remaining - unit * (count - 1)

    to_create: list[Installment] = []

    for i in range(1, count + 1):
        due_date = _due_date(booking, i)
        amount   = unit if i < count else last_amount
        challan  = _challan_number(project_code, booking.pk, i)

        to_create.append(
            Installment(
                booking=booking,
                challan_number=challan,
                installment_number=i,
                due_date=due_date,
                amount_due=amount,
                # amount_paid / paid_on / status stay at model defaults
            )
        )

    Installment.objects.bulk_create(to_create)
    return to_create


# ─────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────

def _due_date(booking: Booking, installment_number: int):
    """
    Lump sum: due 30 calendar days after booking_date.
    Monthly plans: due N months after booking_date (month 1, 2, … N).
    """
    if booking.payment_plan == Booking.PaymentPlan.LUMP_SUM:
        return booking.booking_date + relativedelta(days=30)
    return booking.booking_date + relativedelta(months=installment_number)


def _challan_number(project_code: str, booking_id: int, installment_no: int) -> str:
    """DLD-{PROJECT_CODE}-{BOOKING_ID:04d}-{INSTALLMENT_NO:03d}"""
    return f'DLD-{project_code}-{booking_id:04d}-{installment_no:03d}'

