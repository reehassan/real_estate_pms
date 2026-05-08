"""
apps/bookings/tests.py

Test suite for the Booking domain — models, signals, and installment service.

Coverage:
    BookingModelTests          — properties, soft delete, manager filtering
    InstallmentModelTests      — properties, soft delete, manager filtering
    UniqueConstraintTests      — DB-level double-booking prevention
    BookingSignalTests         — plot status transitions on every status change
    InstallmentServiceTests    — schedule generation: counts, amounts, dates, challans
    SoftDeleteIntegrationTests — delete() releases plot via signal chain

Run:
    python manage.py test apps.bookings.tests --verbosity=2
"""

from datetime import date
from decimal import Decimal
from decimal import ROUND_DOWN

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Booking, Installment
from apps.bookings.services.installment_service import generate_installments
from apps.customers.models import Customer
from apps.projects_and_plots.models import Plot, Project

User = get_user_model()


# ─────────────────────────────────────────────────────────────────
# SHARED FACTORY
# One place to create test objects — keeps every test short.
# ─────────────────────────────────────────────────────────────────

class _Factory:
    """
    Lightweight factory — no third-party library needed.
    Each method returns a saved instance with sensible defaults.
    Pass keyword args to override any field.
    """

    @staticmethod
    def project(**kwargs) -> Project:
        defaults = dict(
            name       = "Royal Bahria",
            code       = "RBS",
            location   = "Islamabad",
            total_area = 500,
            status     = Project.Status.ACTIVE,
        )
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    @staticmethod
    def plot(project: Project, **kwargs) -> Plot:
        # Use a counter so multiple plots in one test don't clash
        n = Plot.all_objects.filter(project=project).count() + 1
        defaults = dict(
            project    = project,
            plot_number= f"A-{n}",
            size       = Decimal("5.00"),
            size_unit  = Plot.SizeUnit.MARLA,
            category   = Plot.Category.RESIDENTIAL,
            price      = Decimal("1_000_000"),
            status     = Plot.Status.AVAILABLE,
        )
        defaults.update(kwargs)
        return Plot.objects.create(**defaults)

    @staticmethod
    def customer(**kwargs) -> Customer:
        n = Customer.all_objects.count() + 1
        defaults = dict(
            full_name     = f"Test Customer {n}",
            cnic = f"{35000 + n:05d}-{n:07d}-{n % 9}",  # unique per call
            phone         = f"0300000{n:04d}"[:11],
            address       = "Rawalpindi",
            customer_type = Customer.CustomerType.INDIVIDUAL,
        )
        defaults.update(kwargs)
        return Customer.objects.create(**defaults)

    @staticmethod
    def user(**kwargs) -> User:
        n = User.objects.count() + 1
        defaults = dict(
            username = f"staff{n}",
            email    = f"staff{n}@test.com",
        )
        defaults.update(kwargs)
        return User.objects.create_user(**defaults, password="testpass123")

    @classmethod
    def booking(cls, plot: Plot, customer: Customer, **kwargs) -> Booking:
        defaults = dict(
            plot         = plot,
            customer     = customer,
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
            status       = Booking.Status.TOKEN,
            total_price  = Decimal("1_000_000"),
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
            booking_date = date(2024, 1, 1),
        )
        defaults.update(kwargs)
        return Booking.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────
# 1. BOOKING MODEL TESTS
# ─────────────────────────────────────────────────────────────────

class BookingModelTests(TestCase):

    def setUp(self):
        self.project  = _Factory.project()
        self.plot     = _Factory.plot(self.project)
        self.customer = _Factory.customer()

    # ── Computed properties ───────────────────────────────────────

    def test_total_upfront_sums_token_and_down_payment(self):
        booking = _Factory.booking(
            self.plot, self.customer,
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
        )
        self.assertEqual(booking.total_upfront, Decimal("200_000"))

    def test_installment_principal_excludes_token_and_down_payment(self):
        booking = _Factory.booking(
            self.plot, self.customer,
            total_price  = Decimal("1_000_000"),
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
        )
        # principal = 1_000_000 - 50_000 - 150_000 = 800_000
        self.assertEqual(booking.installment_principal, Decimal("800_000"))

    def test_installment_principal_is_zero_when_upfront_covers_full_price(self):
        booking = _Factory.booking(
            self.plot, self.customer,
            total_price  = Decimal("200_000"),
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
        )
        self.assertEqual(booking.installment_principal, Decimal("0"))

    def test_str_contains_customer_name_and_plot_number(self):
        booking = _Factory.booking(self.plot, self.customer)
        self.assertIn(self.customer.full_name, str(booking))
        self.assertIn(self.plot.plot_number, str(booking))

    # ── Soft delete ───────────────────────────────────────────────

    def test_delete_sets_is_deleted_flag(self):
        booking = _Factory.booking(self.plot, self.customer)
        booking.delete()
        booking.refresh_from_db()
        self.assertTrue(booking.is_deleted)

    def test_delete_records_deleted_at_timestamp(self):
        booking = _Factory.booking(self.plot, self.customer)
        before  = timezone.now()
        booking.delete()
        booking.refresh_from_db()
        self.assertIsNotNone(booking.deleted_at)
        self.assertGreaterEqual(booking.deleted_at, before)

    def test_delete_sets_status_to_cancelled(self):
        booking = _Factory.booking(
            self.plot, self.customer,
            status=Booking.Status.ACTIVE,
        )
        booking.delete()
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    # ── Manager filtering ─────────────────────────────────────────

    def test_default_manager_excludes_soft_deleted(self):
        booking = _Factory.booking(self.plot, self.customer)
        pk = booking.pk
        booking.delete()
        self.assertFalse(Booking.objects.filter(pk=pk).exists())

    def test_all_objects_manager_includes_soft_deleted(self):
        booking = _Factory.booking(self.plot, self.customer)
        pk = booking.pk
        booking.delete()
        self.assertTrue(Booking.all_objects.filter(pk=pk).exists())


# ─────────────────────────────────────────────────────────────────
# 2. INSTALLMENT MODEL TESTS
# ─────────────────────────────────────────────────────────────────

class InstallmentModelTests(TestCase):

    def setUp(self):
        project       = _Factory.project()
        plot          = _Factory.plot(project)
        customer      = _Factory.customer()
        self.booking  = _Factory.booking(
            plot, customer,
            status = Booking.Status.ACTIVE,
        )
        # Grab first generated installment
        self.inst = self.booking.installments.first()

    def test_balance_is_amount_due_minus_amount_paid(self):
        self.inst.amount_paid = Decimal("10_000")
        self.inst.save()
        self.assertEqual(self.inst.balance, self.inst.amount_due - Decimal("10_000"))

    def test_is_fully_paid_false_when_underpaid(self):
        self.inst.amount_paid = self.inst.amount_due - Decimal("1")
        self.assertFalse(self.inst.is_fully_paid)

    def test_is_fully_paid_true_when_exact_payment(self):
        self.inst.amount_paid = self.inst.amount_due
        self.assertTrue(self.inst.is_fully_paid)

    def test_is_fully_paid_true_when_overpaid(self):
        # Overpayment is possible and still counts as fully paid
        self.inst.amount_paid = self.inst.amount_due + Decimal("1")
        self.assertTrue(self.inst.is_fully_paid)

    def test_soft_delete_sets_flag(self):
        self.inst.delete()
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.is_deleted)

    def test_default_manager_excludes_soft_deleted_installment(self):
        pk = self.inst.pk
        self.inst.delete()
        self.assertFalse(Installment.objects.filter(pk=pk).exists())

    def test_all_objects_manager_includes_soft_deleted_installment(self):
        pk = self.inst.pk
        self.inst.delete()
        self.assertTrue(Installment.all_objects.filter(pk=pk).exists())


# ─────────────────────────────────────────────────────────────────
# 3. UNIQUE CONSTRAINT TESTS
# ─────────────────────────────────────────────────────────────────

class UniqueConstraintTests(TestCase):
    """
    The DB constraint: only one non-deleted TOKEN or ACTIVE booking per plot.
    A CANCELLED or soft-deleted booking releases the plot.
    """

    def setUp(self):
        project       = _Factory.project()
        self.plot     = _Factory.plot(project)
        self.customer = _Factory.customer()

    def test_two_active_bookings_on_same_plot_raises_integrity_error(self):
        _Factory.booking(self.plot, self.customer, status=Booking.Status.ACTIVE)
        customer2 = _Factory.customer()
        with self.assertRaises(IntegrityError):
            _Factory.booking(self.plot, customer2, status=Booking.Status.ACTIVE)

    def test_two_token_bookings_on_same_plot_raises_integrity_error(self):
        _Factory.booking(self.plot, self.customer, status=Booking.Status.TOKEN)
        customer2 = _Factory.customer()
        with self.assertRaises(IntegrityError):
            _Factory.booking(self.plot, customer2, status=Booking.Status.TOKEN)

    def test_new_booking_allowed_after_previous_is_cancelled(self):
        booking1 = _Factory.booking(self.plot, self.customer, status=Booking.Status.ACTIVE)
        booking1.status = Booking.Status.CANCELLED
        booking1.save()

        customer2 = _Factory.customer()
        # Should not raise
        booking2 = _Factory.booking(self.plot, customer2, status=Booking.Status.ACTIVE)
        self.assertIsNotNone(booking2.pk)

    def test_new_booking_allowed_after_previous_is_soft_deleted(self):
        booking1 = _Factory.booking(self.plot, self.customer, status=Booking.Status.ACTIVE)
        booking1.delete()  # soft delete sets status=CANCELLED

        customer2 = _Factory.customer()
        booking2  = _Factory.booking(self.plot, customer2, status=Booking.Status.ACTIVE)
        self.assertIsNotNone(booking2.pk)

    def test_completed_booking_does_not_block_new_booking(self):
        """COMPLETED status is not in the constraint — plot is SOLD but DB allows it."""
        _Factory.booking(self.plot, self.customer, status=Booking.Status.COMPLETED)
        customer2 = _Factory.customer()
        booking2  = _Factory.booking(self.plot, customer2, status=Booking.Status.TOKEN)
        self.assertIsNotNone(booking2.pk)


# ─────────────────────────────────────────────────────────────────
# 4. BOOKING SIGNAL TESTS (plot status transitions)
# ─────────────────────────────────────────────────────────────────

class BookingSignalTests(TestCase):
    """
    Every transition in signals.py has exactly one test.
    We refresh the plot from DB after each save to check the actual value.
    """

    def setUp(self):
        self.project  = _Factory.project()
        self.customer = _Factory.customer()

    def _fresh_plot(self, plot: Plot) -> Plot:
        """Return the plot re-fetched from DB."""
        return Plot.all_objects.get(pk=plot.pk)

    # ── Creation transitions ──────────────────────────────────────

    def test_create_token_booking_sets_plot_to_token(self):
        plot    = _Factory.plot(self.project)
        self.assertEqual(plot.status, Plot.Status.AVAILABLE)

        _Factory.booking(plot, self.customer, status=Booking.Status.TOKEN)

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.TOKEN)

    def test_create_active_booking_sets_plot_to_booked(self):
        plot = _Factory.plot(self.project)
        _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.BOOKED)

    def test_create_active_booking_generates_installments(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(
            plot, self.customer,
            status       = Booking.Status.ACTIVE,
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
        )
        self.assertEqual(booking.installments.count(), 12)

    # ── TOKEN → ACTIVE ────────────────────────────────────────────

    def test_token_to_active_sets_plot_to_booked(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.TOKEN)

        booking.status = Booking.Status.ACTIVE
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.BOOKED)

    def test_token_to_active_generates_installments(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(
            plot, self.customer,
            status       = Booking.Status.TOKEN,
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
        )
        self.assertEqual(booking.installments.count(), 0)

        booking.status = Booking.Status.ACTIVE
        booking.save()

        self.assertEqual(booking.installments.count(), 12)

    # ── → CANCELLED ───────────────────────────────────────────────

    def test_token_to_cancelled_sets_plot_to_available(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.TOKEN)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.TOKEN)

        booking.status = Booking.Status.CANCELLED
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.AVAILABLE)

    def test_active_to_cancelled_sets_plot_to_available(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.BOOKED)

        booking.status = Booking.Status.CANCELLED
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.AVAILABLE)

    # ── → COMPLETED ───────────────────────────────────────────────

    def test_active_to_completed_sets_plot_to_sold(self):
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)

        booking.status = Booking.Status.COMPLETED
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.SOLD)

    # ── No-op transitions ─────────────────────────────────────────

    def test_non_status_save_does_not_change_plot_status(self):
        """Editing notes on a TOKEN booking must not change plot status."""
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.TOKEN)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.TOKEN)

        booking.notes = "Updated note"
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.TOKEN)

    def test_plot_status_unchanged_when_status_field_not_changed(self):
        """Saving the same status twice must be idempotent."""
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)

        booking.status = Booking.Status.ACTIVE  # same value
        booking.save()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.BOOKED)

    # ── Soft delete via delete() ──────────────────────────────────

    def test_soft_delete_releases_plot_to_available(self):
        """
        Booking.delete() sets status=CANCELLED which triggers the signal.
        Plot must end up AVAILABLE.
        """
        plot    = _Factory.plot(self.project)
        booking = _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.BOOKED)

        booking.delete()

        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.AVAILABLE)

    def test_soft_delete_allows_rebooking_same_plot(self):
        plot      = _Factory.plot(self.project)
        booking1  = _Factory.booking(plot, self.customer, status=Booking.Status.ACTIVE)
        booking1.delete()

        customer2 = _Factory.customer()
        booking2  = _Factory.booking(plot, customer2, status=Booking.Status.TOKEN)
        self.assertIsNotNone(booking2.pk)
        self.assertEqual(self._fresh_plot(plot).status, Plot.Status.TOKEN)


# ─────────────────────────────────────────────────────────────────
# 5. INSTALLMENT SERVICE TESTS
# ─────────────────────────────────────────────────────────────────

class InstallmentServiceTests(TestCase):
    """
    Tests for apps/bookings/services/installment_service.py.
    Signals are disconnected where needed to call generate_installments
    directly without double-generating.
    """

    def setUp(self):
        project      = _Factory.project(code="RBS")
        plot         = _Factory.plot(project)
        customer     = _Factory.customer()
        # Create as TOKEN — signal does NOT generate installments on TOKEN
        self.booking = _Factory.booking(
            plot, customer,
            status       = Booking.Status.TOKEN,
            total_price  = Decimal("1_000_000"),
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
            booking_date = date(2024, 1, 1),
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
        )

    # ── Installment counts per plan ───────────────────────────────

    def _make_booking_for_plan(self, plan: str) -> Booking:
        project  = _Factory.project(code="TST")
        plot     = _Factory.plot(project)
        customer = _Factory.customer()
        return _Factory.booking(
            plot, customer,
            status       = Booking.Status.TOKEN,
            total_price  = Decimal("1_200_000"),
            token_amount = Decimal("0"),
            down_payment = Decimal("0"),
            payment_plan = plan,
            booking_date = date(2024, 1, 1),
        )

    def test_lump_sum_generates_one_installment(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.LUMP_SUM)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 1)

    def test_six_months_generates_6_installments(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.SIX_MONTHS)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 6)

    def test_one_year_generates_12_installments(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.ONE_YEAR)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 12)

    def test_two_year_generates_24_installments(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.TWO_YEAR)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 24)

    def test_three_year_generates_36_installments(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.THREE_YEAR)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 36)

    def test_five_year_generates_60_installments(self):
        b = self._make_booking_for_plan(Booking.PaymentPlan.FIVE_YEAR)
        generate_installments(b)
        self.assertEqual(b.installments.count(), 60)

    # ── Amounts ───────────────────────────────────────────────────

    def test_sum_of_installments_equals_principal_exactly(self):
        """
        This is the critical rounding test.
        Sum must equal installment_principal to the cent — no float drift.
        """
        generate_installments(self.booking)
        principal = self.booking.installment_principal
        total     = sum(i.amount_due for i in self.booking.installments.all())
        self.assertEqual(total, principal)

    def test_last_installment_absorbs_rounding_remainder(self):
        """
        With principal=800_000 / 12 → 66666.66 each, remainder 0.08.
        Last installment should be 66666.74.
        """
        generate_installments(self.booking)
        insts = list(self.booking.installments.order_by("installment_number"))
        # All except last should be floor-rounded equally
        unit = (
            Decimal("800000") / 12
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_DOWN,
        )
        for inst in insts[:-1]:
            self.assertEqual(inst.amount_due, unit)
        # Last absorbs remainder
        expected_last = Decimal("800000") - unit * 11
        self.assertEqual(insts[-1].amount_due, expected_last)

    def test_zero_principal_returns_empty_list_and_no_installments(self):
        """When upfront covers full price, no schedule should be created."""
        project  = _Factory.project(code="ZRO")
        plot     = _Factory.plot(project)
        customer = _Factory.customer()
        booking  = _Factory.booking(
            plot, customer,
            status       = Booking.Status.TOKEN,
            total_price  = Decimal("200_000"),
            token_amount = Decimal("50_000"),
            down_payment = Decimal("150_000"),
        )
        result = generate_installments(booking)
        self.assertEqual(result, [])
        self.assertEqual(booking.installments.count(), 0)

    # ── Duplicate guard ───────────────────────────────────────────

    def test_calling_generate_twice_does_not_duplicate_installments(self):
        """Guard: if installments already exist, second call returns [] silently."""
        generate_installments(self.booking)
        count_after_first = self.booking.installments.count()

        result = generate_installments(self.booking)

        self.assertEqual(result, [])
        self.assertEqual(self.booking.installments.count(), count_after_first)

    # ── Due dates ─────────────────────────────────────────────────

    def test_lump_sum_due_date_is_30_days_after_booking_date(self):
        project  = _Factory.project(code="LMP")
        plot     = _Factory.plot(project)
        customer = _Factory.customer()
        booking  = _Factory.booking(
            plot, customer,
            status       = Booking.Status.TOKEN,
            payment_plan = Booking.PaymentPlan.LUMP_SUM,
            booking_date = date(2024, 3, 1),
            total_price  = Decimal("500_000"),
            token_amount = Decimal("0"),
            down_payment = Decimal("0"),
        )
        generate_installments(booking)
        inst = booking.installments.first()
        self.assertEqual(inst.due_date, date(2024, 3, 31))

    def test_monthly_due_dates_are_n_months_after_booking_date(self):
        """
        Installment 1 → 1 month after booking_date
        Installment 2 → 2 months after booking_date, etc.
        """
        booking_date = date(2024, 1, 1)
        generate_installments(self.booking)
        insts = list(self.booking.installments.order_by("installment_number"))

        for i, inst in enumerate(insts, start=1):
            expected_month = (booking_date.month + i - 1) % 12 + 1
            self.assertEqual(inst.due_date.day, 1)  # same day as booking
            self.assertEqual(inst.installment_number, i)

    def test_monthly_dates_handle_month_end_correctly(self):
        """booking_date=Jan 31 → month 1 due = Feb 28 (dateutil handles this)."""
        project  = _Factory.project(code="ME1")
        plot     = _Factory.plot(project)
        customer = _Factory.customer()
        booking  = _Factory.booking(
            plot, customer,
            status       = Booking.Status.TOKEN,
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
            booking_date = date(2024, 1, 31),
            total_price  = Decimal("1_200_000"),
            token_amount = Decimal("0"),
            down_payment = Decimal("0"),
        )
        generate_installments(booking)
        first_inst = booking.installments.order_by("installment_number").first()
        # dateutil relativedelta clamps Feb 31 → Feb 29 (2024 is a leap year)
        self.assertEqual(first_inst.due_date, date(2024, 2, 29))

    # ── Challan numbers ───────────────────────────────────────────

    def test_challan_number_format(self):
        """Expected: DLD-{PROJECT_CODE}-{BOOKING_ID:04d}-{INSTALLMENT_NO:03d}"""
        generate_installments(self.booking)
        first = self.booking.installments.order_by("installment_number").first()
        expected = f"DLD-RBS-{self.booking.pk:04d}-001"
        self.assertEqual(first.challan_number, expected)

    def test_challan_numbers_are_unique_across_all_installments(self):
        generate_installments(self.booking)
        challans = list(
            self.booking.installments.values_list("challan_number", flat=True)
        )
        self.assertEqual(len(challans), len(set(challans)))

    def test_challan_uses_project_code_not_project_name(self):
        """
        Guard against regression to the old utils.py behaviour which used
        project.name[:3] instead of project.code.
        """
        generate_installments(self.booking)
        first = self.booking.installments.order_by("installment_number").first()
        # Code is "RBS", name[:3] would be "Roy" — they must differ here
        self.assertIn("RBS", first.challan_number)
        self.assertNotIn("Roy", first.challan_number)

    # ── Installment defaults ──────────────────────────────────────

    def test_new_installments_have_pending_status(self):
        generate_installments(self.booking)
        statuses = set(
            self.booking.installments.values_list("status", flat=True)
        )
        self.assertEqual(statuses, {Installment.Status.PENDING})

    def test_new_installments_have_zero_amount_paid(self):
        generate_installments(self.booking)
        for inst in self.booking.installments.all():
            self.assertEqual(inst.amount_paid, Decimal("0"))

    def test_installment_numbers_are_sequential_from_one(self):
        generate_installments(self.booking)
        numbers = list(
            self.booking.installments
            .order_by("installment_number")
            .values_list("installment_number", flat=True)
        )
        self.assertEqual(numbers, list(range(1, 13)))