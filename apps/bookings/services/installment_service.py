"""
apps/bookings/services/installment_service.py

Installment generation logic.
Called by post_save signal on Booking when status transitions to ACTIVE.

Rounding strategy:
    Each installment is floor-rounded to 2 decimal places.
    The last installment absorbs the remainder so that:
        sum(amount_due) == installment_principal  (exactly)

    installment_principal = total_price - token_amount - down_payment
"""

from decimal import Decimal, ROUND_DOWN
from dateutil.relativedelta import relativedelta

from apps.bookings.models import Booking, Installment


# Maps payment plan → number of installments
_PLAN_COUNT: dict[str, int] = {
    Booking.PaymentPlan.LUMP_SUM:    1,
    Booking.PaymentPlan.SIX_MONTHS:  6,
    Booking.PaymentPlan.ONE_YEAR:    12,
    Booking.PaymentPlan.TWO_YEAR:    24,
    Booking.PaymentPlan.THREE_YEAR:  36,
    Booking.PaymentPlan.FIVE_YEAR:   60,
}


def generate_installments(booking: Booking) -> list[Installment]:
    """
    Generate and bulk-create the installment schedule for a booking.

    Rules:
        - token_amount + down_payment are excluded from the schedule.
        - installment_principal = total_price - token_amount - down_payment
        - Lump sum  → 1 installment due 30 days from booking_date.
        - 3yr / 5yr → monthly installments starting 1 month after booking_date.
        - Remainder from Decimal division is absorbed by the last installment.
        - Only called when booking transitions to ACTIVE — never on TOKEN status.

    Returns:
        List of created Installment instances (empty if principal is zero).

    Raises:
        KeyError:   if payment_plan is not a recognised choice.
        ValueError: if installments already exist for this booking.
    """
    # Guard: never regenerate if installments already exist
    if Installment.all_objects.filter(booking=booking).exists():
        return []

    # Use the model property — token + down_payment both excluded
    remaining: Decimal = booking.installment_principal

    if remaining <= 0:
        # Fully covered by token + down payment — no schedule needed
        return []

    count: int = _PLAN_COUNT[booking.payment_plan]
    project_code: str = booking.plot.project.code

    unit: Decimal        = (remaining / count).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    last_amount: Decimal = remaining - unit * (count - 1)

    to_create: list[Installment] = []
    for i in range(1, count + 1):
        due_date = _due_date(booking, i)
        amount   = unit if i < count else last_amount
        challan  = _challan_number(project_code, booking.pk, i)

        to_create.append(
            Installment(
                booking            = booking,
                challan_number     = challan,
                installment_number = i,
                due_date           = due_date,
                amount_due         = amount,
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