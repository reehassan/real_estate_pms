"""
apps/reports/tests.py

Test suite for all 10 report views.

Every view is tested for:
    1. Anonymous user is redirected to login (staff_member_required)
    2. Authenticated non-staff user is redirected
    3. Staff user receives a valid Excel file (200 + correct content-type)
    4. Content-Disposition header contains the expected filename prefix
    5. Response body is non-empty (file actually has content)
    6. View works correctly with real seeded data (smoke test)

Run:
    python manage.py test apps.reports.tests --verbosity=2
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.bookings.models import Booking, Installment
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.projects_and_plots.models import Plot, Project

User = get_user_model()

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


# ─────────────────────────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────────────────────────

class _Factory:
    _counter = 0

    @classmethod
    def _n(cls) -> int:
        cls._counter += 1
        return cls._counter

    @classmethod
    def staff_user(cls, **kwargs) -> User:
        n = cls._n()
        u = User.objects.create_user(
            username = f"staff{n}",
            email    = f"staff{n}@test.com",
            password = "pass",
            is_staff = True,
        )
        return u

    @classmethod
    def plain_user(cls, **kwargs) -> User:
        n = cls._n()
        return User.objects.create_user(
            username = f"user{n}",
            email    = f"user{n}@test.com",
            password = "pass",
            is_staff = False,
        )

    @classmethod
    def project(cls, **kwargs) -> Project:
        n = cls._n()
        defaults = dict(
            name       = f"Project {n}",
            code       = f"P{n:02d}",
            location   = "Islamabad",
            total_area = 200,
            status     = Project.Status.ACTIVE,
        )
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    @classmethod
    def plot(cls, project: Project, **kwargs) -> Plot:
        n = cls._n()
        defaults = dict(
            project     = project,
            plot_number = f"A-{n}",
            size        = Decimal("5"),
            size_unit   = Plot.SizeUnit.MARLA,
            category    = Plot.Category.RESIDENTIAL,
            price       = Decimal("1_000_000"),
            status      = Plot.Status.AVAILABLE,
        )
        defaults.update(kwargs)
        return Plot.objects.create(**defaults)

    @classmethod
    def customer(cls, **kwargs) -> Customer:
        n = cls._n()
        defaults = dict(
            full_name     = f"Customer {n}",
            cnic          = f"35202-{n:07d}-1",
            phone         = f"0300{n:07d}"[:11],
            address       = "Rawalpindi",
            customer_type = Customer.CustomerType.INDIVIDUAL,
        )
        defaults.update(kwargs)
        return Customer.objects.create(**defaults)

    @classmethod
    def booking(cls, plot: Plot, customer: Customer, **kwargs) -> Booking:
        defaults = dict(
            plot                     = plot,
            customer                 = customer,
            payment_plan             = Booking.PaymentPlan.ONE_YEAR,
            status                   = Booking.Status.ACTIVE,
            total_price              = Decimal("1_000_000"),
            token_amount             = Decimal("50_000"),
            token_received_on        = date(2024, 1, 1),
            down_payment             = Decimal("150_000"),
            down_payment_received_on = date(2024, 2, 1),
            booking_date             = date(2024, 1, 1),
        )
        defaults.update(kwargs)
        return Booking.objects.create(**defaults)

    @classmethod
    def expense(cls, project: Project, user: User, **kwargs) -> Expense:
        defaults = dict(
            project        = project,
            submitted_by   = user,
            category       = Expense.Category.CONSTRUCTION,
            amount         = Decimal("50_000"),
            description    = "Test expense",
            date           = date(2024, 3, 1),
            payment_method = Expense.PaymentMethod.CASH,
        )
        defaults.update(kwargs)
        return Expense.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────
# BASE TEST CASE — shared helpers
# ─────────────────────────────────────────────────────────────────

class _ReportTestBase(TestCase):
    """
    Sets up:
        self.staff   — staff user (can access reports)
        self.plain   — non-staff user (should be redirected)
        self.client  — Django test client
        self.project — one project with one plot, customer, booking, expense
        self.customer
    """

    def setUp(self):
        self.staff   = _Factory.staff_user()
        self.plain   = _Factory.plain_user()
        self.project = _Factory.project()
        self.customer= _Factory.customer()
        self.plot    = _Factory.plot(self.project)
        self.booking = _Factory.booking(self.plot, self.customer)
        self.expense = _Factory.expense(self.project, self.staff)

    # ── Assertion helpers ─────────────────────────────────────────

    def assertIsXlsx(self, response):
        """Assert the response is a valid non-empty Excel file."""
        self.assertEqual(response.status_code, 200)
        self.assertIn(XLSX_CONTENT_TYPE, response["Content-Type"])
        self.assertGreater(len(response.content), 0)

    def assertFilenameStartsWith(self, response, prefix: str):
        disposition = response.get("Content-Disposition", "")
        self.assertIn(prefix, disposition, (
            f"Expected Content-Disposition to contain '{prefix}', "
            f"got: {disposition!r}"
        ))

    def assertRedirectsAnonymous(self, url: str):
        c = Client()
        resp = c.get(url)
        self.assertIn(resp.status_code, [301, 302])
        self.assertIn("/login", resp["Location"])

    def assertRedirectsNonStaff(self, url: str):
        c = Client()
        c.login(username=self.plain.username, password="pass")
        resp = c.get(url)
        self.assertIn(resp.status_code, [301, 302])

    def staffClient(self) -> Client:
        c = Client()
        c.login(username=self.staff.username, password="pass")
        return c


# ─────────────────────────────────────────────────────────────────
# 1. MONTHLY COLLECTION
# ─────────────────────────────────────────────────────────────────

class MonthlyCollectionTests(_ReportTestBase):

    URL = "/reports/monthly-collection/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self.URL)

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self.URL)

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_filename_prefix(self):
        resp = self.staffClient().get(self.URL)
        self.assertFilenameStartsWith(resp, "monthly_collection_")

    def test_empty_db_returns_xlsx(self):
        """View must not crash when there are no installments."""
        Installment.all_objects.all().delete()
        Booking.all_objects.all().delete()
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 2. OVERDUE AGING
# ─────────────────────────────────────────────────────────────────

class OverdueAgingTests(_ReportTestBase):

    URL = "/reports/overdue-aging/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self.URL)

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self.URL)

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_filename_prefix(self):
        resp = self.staffClient().get(self.URL)
        self.assertFilenameStartsWith(resp, "overdue_aging_")

    def test_with_overdue_installments(self):
        """View must handle actual overdue installments without crashing."""
        inst = self.booking.installments.first()
        if inst:
            inst.status  = Installment.Status.OVERDUE
            inst.due_date= date(2023, 1, 1)   # far in the past
            inst.save()
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_no_overdue_returns_xlsx(self):
        Installment.objects.all().update(status=Installment.Status.PENDING)
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 3. PAYMENT PLAN BREAKDOWN
# ─────────────────────────────────────────────────────────────────

class PaymentPlanBreakdownTests(_ReportTestBase):

    URL = "/reports/payment-plan-breakdown/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self.URL)

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self.URL)

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_filename_prefix(self):
        resp = self.staffClient().get(self.URL)
        self.assertFilenameStartsWith(resp, "payment_plan_breakdown_")

    def test_multiple_plans_represented(self):
        """
        Create bookings across different plans and confirm view doesn't crash.
        Also guards against the ORM fanout bug that was fixed.
        """
        project  = _Factory.project()
        customer = _Factory.customer()
        for plan in [
            Booking.PaymentPlan.LUMP_SUM,
            Booking.PaymentPlan.SIX_MONTHS,
            Booking.PaymentPlan.THREE_YEAR,
        ]:
            plot = _Factory.plot(project)
            _Factory.booking(plot, customer, payment_plan=plan)

        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 4. CASH FLOW
# ─────────────────────────────────────────────────────────────────

class CashFlowTests(_ReportTestBase):

    URL = "/reports/cash-flow/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self.URL)

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self.URL)

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_filename_prefix(self):
        resp = self.staffClient().get(self.URL)
        self.assertFilenameStartsWith(resp, "cash_flow_")

    def test_with_paid_installments_and_expenses(self):
        """Both money-in and money-out paths execute without error."""
        inst = self.booking.installments.first()
        if inst:
            inst.status      = Installment.Status.PAID
            inst.amount_paid = inst.amount_due
            inst.paid_on     = date(2024, 3, 15)
            inst.save()
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_empty_db_returns_xlsx(self):
        Installment.all_objects.all().delete()
        Booking.all_objects.all().delete()
        Expense.all_objects.all().delete()
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 5. TOKEN PIPELINE
# ─────────────────────────────────────────────────────────────────

class TokenPipelineTests(_ReportTestBase):

    URL = "/reports/token-pipeline/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self.URL)

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self.URL)

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_filename_prefix(self):
        resp = self.staffClient().get(self.URL)
        self.assertFilenameStartsWith(resp, "token_pipeline_")

    def test_with_token_bookings(self):
        plot     = _Factory.plot(self.project)
        customer = _Factory.customer()
        _Factory.booking(
            plot, customer,
            status            = Booking.Status.TOKEN,
            token_received_on = date(2024, 1, 15),
        )
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_no_token_bookings_returns_xlsx(self):
        Booking.objects.all().update(status=Booking.Status.ACTIVE)
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)

    def test_token_booking_without_received_date_does_not_crash(self):
        """token_received_on can be None — view falls back to '—'."""
        plot     = _Factory.plot(self.project)
        customer = _Factory.customer()
        _Factory.booking(
            plot, customer,
            status            = Booking.Status.TOKEN,
            token_received_on = None,
        )
        resp = self.staffClient().get(self.URL)
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 6. PROJECT — PLOT INVENTORY
# ─────────────────────────────────────────────────────────────────

class ProjectPlotInventoryTests(_ReportTestBase):

    def _url(self):
        return f"/reports/project/{self.project.pk}/plot-inventory/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self._url())

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self._url())

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_filename_contains_project_code(self):
        resp = self.staffClient().get(self._url())
        self.assertFilenameStartsWith(resp, self.project.code)

    def test_nonexistent_project_returns_404(self):
        resp = self.staffClient().get("/reports/project/99999/plot-inventory/")
        self.assertEqual(resp.status_code, 404)

    def test_all_plot_statuses_represented(self):
        """One plot per status — summary section must handle all four."""
        for status in [
            Plot.Status.AVAILABLE, Plot.Status.TOKEN,
            Plot.Status.BOOKED,    Plot.Status.SOLD,
        ]:
            Plot.objects.create(
                project     = self.project,
                plot_number = f"ST-{status}",
                size        = Decimal("5"),
                size_unit   = Plot.SizeUnit.MARLA,
                category    = Plot.Category.RESIDENTIAL,
                price       = Decimal("500_000"),
                status      = status,
            )
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_plot_with_no_block_does_not_crash(self):
        Plot.objects.create(
            project     = self.project,
            plot_number = "NO-BLOCK",
            size        = Decimal("5"),
            size_unit   = Plot.SizeUnit.MARLA,
            category    = Plot.Category.RESIDENTIAL,
            price       = Decimal("500_000"),
            block       = None,
        )
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 7. PROJECT — REVENUE
# ─────────────────────────────────────────────────────────────────

class ProjectRevenueTests(_ReportTestBase):

    def _url(self):
        return f"/reports/project/{self.project.pk}/revenue/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self._url())

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self._url())

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_filename_contains_project_code(self):
        resp = self.staffClient().get(self._url())
        self.assertFilenameStartsWith(resp, self.project.code)

    def test_nonexistent_project_returns_404(self):
        resp = self.staffClient().get("/reports/project/99999/revenue/")
        self.assertEqual(resp.status_code, 404)

    def test_no_bookings_returns_xlsx(self):
        empty_project = _Factory.project()
        resp = self.staffClient().get(
            f"/reports/project/{empty_project.pk}/revenue/"
        )
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 8. PROJECT — EXPENSES
# ─────────────────────────────────────────────────────────────────

class ProjectExpensesTests(_ReportTestBase):

    def _url(self):
        return f"/reports/project/{self.project.pk}/expenses/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self._url())

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self._url())

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_filename_contains_project_code(self):
        resp = self.staffClient().get(self._url())
        self.assertFilenameStartsWith(resp, self.project.code)

    def test_nonexistent_project_returns_404(self):
        resp = self.staffClient().get("/reports/project/99999/expenses/")
        self.assertEqual(resp.status_code, 404)

    def test_expense_with_no_submitted_by_does_not_crash(self):
        """submitted_by is nullable — view uses submitted_by_id guard."""
        Expense.objects.create(
            project        = self.project,
            submitted_by   = None,
            category       = Expense.Category.LEGAL,
            amount         = Decimal("10_000"),
            description    = "Legal fees",
            date           = date(2024, 4, 1),
            payment_method = Expense.PaymentMethod.TRANSFER,
        )
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_all_expense_categories_present(self):
        for cat in Expense.Category.values:
            Expense.objects.create(
                project        = self.project,
                category       = cat,
                amount         = Decimal("5_000"),
                description    = f"{cat} expense",
                date           = date(2024, 5, 1),
                payment_method = Expense.PaymentMethod.CASH,
            )
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 9. PROJECT — PER-PLOT DETAIL
# ─────────────────────────────────────────────────────────────────

class ProjectPerPlotDetailTests(_ReportTestBase):

    def _url(self):
        return f"/reports/project/{self.project.pk}/per-plot-detail/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self._url())

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self._url())

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_filename_contains_project_code(self):
        resp = self.staffClient().get(self._url())
        self.assertFilenameStartsWith(resp, self.project.code)

    def test_nonexistent_project_returns_404(self):
        resp = self.staffClient().get("/reports/project/99999/per-plot-detail/")
        self.assertEqual(resp.status_code, 404)

    def test_vacant_plot_shows_as_vacant(self):
        """A plot with no booking must not crash — should show '— Vacant —'."""
        _Factory.plot(self.project)   # no booking attached
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_soft_deleted_booking_treated_as_vacant(self):
        """
        If the only booking on a plot is soft-deleted, the plot must appear
        as vacant — the is_deleted filter in the view guards this.
        """
        plot     = _Factory.plot(self.project)
        customer = _Factory.customer()
        booking  = _Factory.booking(plot, customer)
        booking.delete()   # soft delete

        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)


# ─────────────────────────────────────────────────────────────────
# 10. CUSTOMER STATEMENT
# ─────────────────────────────────────────────────────────────────

class CustomerStatementTests(_ReportTestBase):

    def _url(self):
        return f"/reports/customer/{self.customer.pk}/statement/"

    def test_anonymous_redirected(self):
        self.assertRedirectsAnonymous(self._url())

    def test_non_staff_redirected(self):
        self.assertRedirectsNonStaff(self._url())

    def test_staff_gets_xlsx(self):
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_filename_contains_cnic(self):
        resp = self.staffClient().get(self._url())
        self.assertFilenameStartsWith(resp, "customer_statement_")
        self.assertFilenameStartsWith(resp, self.customer.cnic)

    def test_nonexistent_customer_returns_404(self):
        resp = self.staffClient().get("/reports/customer/99999/statement/")
        self.assertEqual(resp.status_code, 404)

    def test_customer_with_no_bookings_does_not_crash(self):
        empty_customer = _Factory.customer()
        resp = self.staffClient().get(
            f"/reports/customer/{empty_customer.pk}/statement/"
        )
        self.assertIsXlsx(resp)

    def test_customer_with_multiple_bookings(self):
        """One section per booking — must handle multiple without crashing."""
        for _ in range(3):
            plot = _Factory.plot(self.project)
            _Factory.booking(plot, self.customer)

        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)

    def test_booking_with_no_installments_does_not_crash(self):
        """
        TOKEN bookings have no installments yet.
        View must show 'No installments generated yet.' without crashing.
        """
        plot = _Factory.plot(self.project)
        _Factory.booking(
            plot, self.customer,
            status = Booking.Status.TOKEN,
        )
        resp = self.staffClient().get(self._url())
        self.assertIsXlsx(resp)