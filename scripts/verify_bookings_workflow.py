import os
import uuid
from datetime import timedelta

import sys

import django
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone


def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    django.setup()


def main():
    setup_django()

    # Local imports after Django setup
    from apps.customers.models import Customer
    from apps.bookings.models import Booking, Installment
    from apps.projects_and_plots.models import Plot, Project
    from django.conf import settings
    from django.db import connections

    today = timezone.localdate()

    # Use a unique suffix so reruns don't collide with unique constraints.
    suffix = uuid.uuid4().hex[:8].upper()

    def make_cnic():
        # CNIC validator requires: 5 digits - 7 digits - 1 digit
        digits = str(uuid.uuid4().int)
        return f"{digits[:5]}-{digits[5:12]}-{digits[12:13]}"

    db_default = settings.DATABASES.get("default", {})
    # Ensure DB is reachable early (will raise an error if not).
    connections["default"].ensure_connection()

    with transaction.atomic():
        # Create shared project
        proj = Project.objects.create(
            name=f"Verify Project {suffix}",
            location=f"Verify Location {suffix}",
            total_area=100,
            area_unit=Project.AreaUnit.MARLA,
        )

        # Test 1: booking created -> plot booked, installments generated
        plot_1 = Plot.objects.create(
            project=proj,
            plot_number=f"VP1-{suffix}",
            size=10.00,
            size_unit=Plot.SizeUnit.MARLA,
            category=Plot.Category.RESIDENTIAL,
            price=100000.00,
            status=Plot.Status.AVAILABLE,
        )
        cust_1 = Customer.objects.create(
            full_name=f"Verify Customer 1 {suffix}",
            cnic=make_cnic(),
            phone="03001234567",
            address="Verify address",
        )
        booking_1 = Booking.objects.create(
            customer=cust_1,
            plot=plot_1,
            total_price=120000.00,
            down_payment=20000.00,
            payment_plan=Booking.PaymentPlan.LUMP_SUM,
            status=Booking.Status.ACTIVE,
        )

        plot_1.refresh_from_db()
        assert plot_1.status == Plot.Status.BOOKED, f"Expected BOOKED, got {plot_1.status}"
        assert booking_1.installments.count() == 1, "Expected 1 installment for lump-sum"

        # Test 2: booking cancelled -> plot available (unless SOLD)
        booking_1.status = Booking.Status.CANCELLED
        booking_1.save()
        plot_1.refresh_from_db()
        assert plot_1.status == Plot.Status.AVAILABLE, f"Expected AVAILABLE, got {plot_1.status}"

        # Test 3: created-as-cancelled guard -> plot should not be reserved
        plot_2 = Plot.objects.create(
            project=proj,
            plot_number=f"VP2-{suffix}",
            size=11.00,
            size_unit=Plot.SizeUnit.MARLA,
            category=Plot.Category.RESIDENTIAL,
            price=110000.00,
            status=Plot.Status.AVAILABLE,
        )
        cust_2 = Customer.objects.create(
            full_name=f"Verify Customer 2 {suffix}",
            cnic=make_cnic(),
            phone="03009876543",
            address="Verify address",
        )
        booking_cancelled_created = Booking.objects.create(
            customer=cust_2,
            plot=plot_2,
            total_price=130000.00,
            down_payment=10000.00,
            payment_plan=Booking.PaymentPlan.LUMP_SUM,
            status=Booking.Status.CANCELLED,
        )
        plot_2.refresh_from_db()
        assert plot_2.status == Plot.Status.AVAILABLE, f"Expected AVAILABLE, got {plot_2.status}"
        assert booking_cancelled_created.installments.count() == 0, "Cancelled booking should not generate installments"

        # Test 4: all installments paid -> booking completed + plot sold
        plot_3 = Plot.objects.create(
            project=proj,
            plot_number=f"VP3-{suffix}",
            size=12.00,
            size_unit=Plot.SizeUnit.MARLA,
            category=Plot.Category.RESIDENTIAL,
            price=120000.00,
            status=Plot.Status.AVAILABLE,
        )
        cust_3 = Customer.objects.create(
            full_name=f"Verify Customer 3 {suffix}",
            cnic=make_cnic(),
            phone="03112223344",
            address="Verify address",
        )
        booking_3 = Booking.objects.create(
            customer=cust_3,
            plot=plot_3,
            total_price=140000.00,
            down_payment=20000.00,
            payment_plan=Booking.PaymentPlan.LUMP_SUM,
            status=Booking.Status.ACTIVE,
        )

        inst = booking_3.installments.get()
        inst.status = Installment.Status.PAID
        inst.save()

        booking_3.refresh_from_db()
        plot_3.refresh_from_db()
        assert booking_3.status == Booking.Status.COMPLETED, f"Expected COMPLETED, got {booking_3.status}"
        assert plot_3.status == Plot.Status.SOLD, f"Expected SOLD, got {plot_3.status}"

        # Guard: cancelling after SOLD should not flip plot back to AVAILABLE
        booking_3.status = Booking.Status.CANCELLED
        booking_3.save()
        plot_3.refresh_from_db()
        assert plot_3.status == Plot.Status.SOLD, f"Expected SOLD after cancellation, got {plot_3.status}"

        # Test 5: mark_overdue
        plot_4 = Plot.objects.create(
            project=proj,
            plot_number=f"VP4-{suffix}",
            size=13.00,
            size_unit=Plot.SizeUnit.MARLA,
            category=Plot.Category.RESIDENTIAL,
            price=130000.00,
            status=Plot.Status.AVAILABLE,
        )
        cust_4 = Customer.objects.create(
            full_name=f"Verify Customer 4 {suffix}",
            cnic=make_cnic(),
            phone="03221112233",
            address="Verify address",
        )

        past_booking_date = today - timedelta(days=60)
        # For lump-sum: due_date = booking_date + 30 days => still in the past.
        booking_4 = Booking.objects.create(
            customer=cust_4,
            plot=plot_4,
            booking_date=past_booking_date,
            total_price=150000.00,
            down_payment=25000.00,
            payment_plan=Booking.PaymentPlan.LUMP_SUM,
            status=Booking.Status.ACTIVE,
        )
        installment_4 = booking_4.installments.get()
        assert installment_4.status == Installment.Status.PENDING
        assert installment_4.due_date < today

    # Run management command outside atomic block to avoid long locks.
    call_command("mark_overdue", verbosity=0)
    installment_4.refresh_from_db()
    assert installment_4.status == Installment.Status.OVERDUE, f"Expected OVERDUE, got {installment_4.status}"

    print("All booking workflow verification checks passed.")


if __name__ == "__main__":
    main()

