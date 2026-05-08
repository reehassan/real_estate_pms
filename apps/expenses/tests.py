"""
apps/expenses/tests.py

Test suite for the Expense model.

Coverage:
    ExpenseModelTests         — fields, __str__, defaults, optional fields, timestamps
    ExpenseAmountTests        — MinValueValidator, decimal precision
    ExpenseCategoryTests      — all Category choices save and display correctly
    ExpensePaymentMethodTests — all PaymentMethod choices save and display correctly
    ExpenseSoftDeleteTests    — delete(), timestamps, manager filtering
    ExpenseFKTests            — submitted_by SET_NULL, project CASCADE

Run:
    python manage.py test apps.expenses.tests --verbosity=2
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.expenses.models import Expense
from apps.projects_and_plots.models import Project

User = get_user_model()


# ─────────────────────────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────────────────────────

class _Factory:
    _counter = 0

    @classmethod
    def project(cls, **kwargs) -> Project:
        cls._counter += 1
        defaults = dict(
            name       = f"Test Project {cls._counter}",
            code       = f"TP{cls._counter:02d}",
            location   = "Islamabad",
            total_area = 100,
            status     = Project.Status.ACTIVE,
        )
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    @classmethod
    def user(cls, **kwargs) -> User:
        cls._counter += 1
        defaults = dict(
            username = f"staff{cls._counter}",
            email    = f"staff{cls._counter}@test.com",
        )
        defaults.update(kwargs)
        return User.objects.create_user(**defaults, password="pass")

    @classmethod
    def expense(cls, project: Project, **kwargs) -> Expense:
        defaults = dict(
            project        = project,
            category       = Expense.Category.CONSTRUCTION,
            amount         = Decimal("50000.00"),
            description    = "Test expense description",
            date           = date(2024, 6, 15),
            payment_method = Expense.PaymentMethod.CASH,
        )
        defaults.update(kwargs)
        return Expense.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────
# 1. EXPENSE MODEL TESTS
# ─────────────────────────────────────────────────────────────────

class ExpenseModelTests(TestCase):

    def setUp(self):
        self.project = _Factory.project()
        self.user    = _Factory.user()
        self.expense = _Factory.expense(
            self.project,
            category       = Expense.Category.CONSTRUCTION,
            amount         = Decimal("75000.00"),
            vendor_name    = "ABC Builders",
            description    = "Foundation work",
            date           = date(2024, 6, 15),
            payment_method = Expense.PaymentMethod.CHEQUE,
            submitted_by   = self.user,
        )

    # ── __str__ ───────────────────────────────────────────────────

    def test_str_contains_category_display(self):
        self.assertIn("Construction", str(self.expense))

    def test_str_contains_project_name(self):
        self.assertIn(self.project.name, str(self.expense))

    def test_str_contains_formatted_amount(self):
        # 75000 → "75,000"
        self.assertIn("75,000", str(self.expense))

    def test_str_format_is_category_project_amount(self):
        expected = f"Construction — {self.project.name} — PKR 75,000"
        self.assertEqual(str(self.expense), expected)

    # ── Defaults ──────────────────────────────────────────────────

    def test_is_deleted_defaults_to_false(self):
        e = _Factory.expense(self.project)
        self.assertFalse(e.is_deleted)

    def test_deleted_at_defaults_to_none(self):
        e = _Factory.expense(self.project)
        self.assertIsNone(e.deleted_at)

    def test_submitted_by_defaults_to_none(self):
        e = _Factory.expense(self.project)
        self.assertIsNone(e.submitted_by)

    # ── Optional fields ───────────────────────────────────────────

    def test_vendor_name_can_be_blank(self):
        e = _Factory.expense(self.project, vendor_name="")
        self.assertEqual(e.vendor_name, "")

    def test_reference_number_can_be_blank(self):
        e = _Factory.expense(self.project, reference_number="")
        self.assertEqual(e.reference_number, "")

    def test_document_can_be_null(self):
        e = _Factory.expense(self.project)
        self.assertFalse(bool(e.document))

    def test_expense_saves_with_only_required_fields(self):
        """vendor_name, reference_number, document, submitted_by all optional."""
        e = Expense.objects.create(
            project        = self.project,
            category       = Expense.Category.UTILITIES,
            amount         = Decimal("1000.00"),
            description    = "Electricity bill",
            date           = date(2024, 7, 1),
            payment_method = Expense.PaymentMethod.CASH,
        )
        self.assertIsNotNone(e.pk)

    # ── Timestamps ────────────────────────────────────────────────

    def test_created_at_set_on_creation(self):
        self.assertIsNotNone(self.expense.created_at)

    def test_updated_at_set_on_creation(self):
        self.assertIsNotNone(self.expense.updated_at)

    def test_updated_at_changes_on_save(self):
        before = self.expense.updated_at
        self.expense.description = "Updated description"
        self.expense.save()
        self.expense.refresh_from_db()
        self.assertGreaterEqual(self.expense.updated_at, before)


# ─────────────────────────────────────────────────────────────────
# 2. AMOUNT VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────

class ExpenseAmountTests(TestCase):

    def setUp(self):
        self.project = _Factory.project()

    def _expense_with_amount(self, amount) -> Expense:
        return Expense(
            project        = self.project,
            category       = Expense.Category.MARKETING,
            amount         = amount,
            description    = "Test",
            date           = date(2024, 1, 1),
            payment_method = Expense.PaymentMethod.CASH,
        )

    # ── Valid amounts ─────────────────────────────────────────────
    def test_positive_amount_passes_validation(self):
        e = self._expense_with_amount(Decimal("1.00"))
        e.full_clean(exclude=["submitted_by"])   # ← exclude nullable FK

    def test_zero_amount_fails_validation(self):
        e = self._expense_with_amount(Decimal("0.00"))
        with self.assertRaises(ValidationError):
            e.full_clean(exclude=["submitted_by"])

    def test_negative_amount_fails_validation(self):
        e = self._expense_with_amount(Decimal("-1.00"))
        with self.assertRaises(ValidationError):
            e.full_clean(exclude=["submitted_by"])

    def test_very_small_negative_fails_validation(self):
        e = self._expense_with_amount(Decimal("-0.01"))
        with self.assertRaises(ValidationError):
            e.full_clean(exclude=["submitted_by"])

    def test_amount_preserves_decimal_precision(self):
        e = _Factory.expense(self.project, amount=Decimal("12345.67"))
        e.refresh_from_db()
        self.assertEqual(e.amount, Decimal("12345.67"))

# ─────────────────────────────────────────────────────────────────
# 3. CATEGORY TESTS
# ─────────────────────────────────────────────────────────────────

class ExpenseCategoryTests(TestCase):

    def setUp(self):
        self.project = _Factory.project()

    def _make(self, category: str) -> Expense:
        return _Factory.expense(self.project, category=category)

    # ── All choices save and retrieve ─────────────────────────────

    def test_construction_saves(self):
        e = self._make(Expense.Category.CONSTRUCTION)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.CONSTRUCTION)

    def test_marketing_saves(self):
        e = self._make(Expense.Category.MARKETING)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.MARKETING)

    def test_salaries_saves(self):
        e = self._make(Expense.Category.SALARIES)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.SALARIES)

    def test_utilities_saves(self):
        e = self._make(Expense.Category.UTILITIES)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.UTILITIES)

    def test_legal_saves(self):
        e = self._make(Expense.Category.LEGAL)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.LEGAL)

    def test_miscellaneous_saves(self):
        e = self._make(Expense.Category.MISCELLANEOUS)
        e.refresh_from_db()
        self.assertEqual(e.category, Expense.Category.MISCELLANEOUS)

    # ── Display labels ────────────────────────────────────────────

    def test_construction_display(self):
        e = self._make(Expense.Category.CONSTRUCTION)
        self.assertEqual(e.get_category_display(), "Construction")

    def test_salaries_display(self):
        e = self._make(Expense.Category.SALARIES)
        self.assertEqual(e.get_category_display(), "Staff Salaries")

    def test_miscellaneous_display(self):
        e = self._make(Expense.Category.MISCELLANEOUS)
        self.assertEqual(e.get_category_display(), "Miscellaneous")


# ─────────────────────────────────────────────────────────────────
# 4. PAYMENT METHOD TESTS
# ─────────────────────────────────────────────────────────────────

class ExpensePaymentMethodTests(TestCase):

    def setUp(self):
        self.project = _Factory.project()

    def _make(self, method: str) -> Expense:
        return _Factory.expense(self.project, payment_method=method)

    def test_cash_saves(self):
        e = self._make(Expense.PaymentMethod.CASH)
        e.refresh_from_db()
        self.assertEqual(e.payment_method, Expense.PaymentMethod.CASH)

    def test_transfer_saves(self):
        e = self._make(Expense.PaymentMethod.TRANSFER)
        e.refresh_from_db()
        self.assertEqual(e.payment_method, Expense.PaymentMethod.TRANSFER)

    def test_cheque_saves(self):
        e = self._make(Expense.PaymentMethod.CHEQUE)
        e.refresh_from_db()
        self.assertEqual(e.payment_method, Expense.PaymentMethod.CHEQUE)

    def test_cash_display(self):
        e = self._make(Expense.PaymentMethod.CASH)
        self.assertEqual(e.get_payment_method_display(), "Cash")

    def test_transfer_display(self):
        e = self._make(Expense.PaymentMethod.TRANSFER)
        self.assertEqual(e.get_payment_method_display(), "Bank Transfer")

    def test_cheque_display(self):
        e = self._make(Expense.PaymentMethod.CHEQUE)
        self.assertEqual(e.get_payment_method_display(), "Cheque")


# ─────────────────────────────────────────────────────────────────
# 5. SOFT DELETE TESTS
# ─────────────────────────────────────────────────────────────────

class ExpenseSoftDeleteTests(TestCase):

    def setUp(self):
        self.project = _Factory.project()
        self.expense = _Factory.expense(self.project)

    def test_delete_sets_is_deleted_to_true(self):
        self.expense.delete()
        self.expense.refresh_from_db()
        self.assertTrue(self.expense.is_deleted)

    def test_delete_sets_deleted_at_timestamp(self):
        before = timezone.now()
        self.expense.delete()
        self.expense.refresh_from_db()
        self.assertIsNotNone(self.expense.deleted_at)
        self.assertGreaterEqual(self.expense.deleted_at, before)

    def test_delete_does_not_remove_row_from_database(self):
        pk = self.expense.pk
        self.expense.delete()
        self.assertTrue(Expense.all_objects.filter(pk=pk).exists())

    def test_delete_preserves_amount(self):
        amount = self.expense.amount
        self.expense.delete()
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.amount, amount)

    def test_default_manager_excludes_deleted_expense(self):
        pk = self.expense.pk
        self.expense.delete()
        self.assertFalse(Expense.objects.filter(pk=pk).exists())

    def test_all_objects_manager_includes_deleted_expense(self):
        pk = self.expense.pk
        self.expense.delete()
        self.assertTrue(Expense.all_objects.filter(pk=pk).exists())

    def test_default_manager_still_returns_non_deleted_expenses(self):
        e2 = _Factory.expense(self.project)
        self.expense.delete()
        pks = list(Expense.objects.values_list("pk", flat=True))
        self.assertNotIn(self.expense.pk, pks)
        self.assertIn(e2.pk, pks)

    def test_delete_is_idempotent(self):
        self.expense.delete()
        try:
            self.expense.delete()
        except Exception as e:
            self.fail(f"Second delete() raised unexpectedly: {e}")

    def test_both_managers_count_after_mixed_deletes(self):
        e2 = _Factory.expense(self.project)
        e3 = _Factory.expense(self.project)
        self.expense.delete()

        self.assertEqual(Expense.objects.count(), 2)       # e2 + e3
        self.assertEqual(Expense.all_objects.count(), 3)   # all three


# ─────────────────────────────────────────────────────────────────
# 6. FOREIGN KEY BEHAVIOUR TESTS
# ─────────────────────────────────────────────────────────────────

class ExpenseFKTests(TestCase):
    """
    submitted_by  → SET_NULL (expense survives if user deleted)
    project       → CASCADE  (expense deleted if project hard-deleted)
    """

    def setUp(self):
        self.project = _Factory.project()
        self.user    = _Factory.user()

    def test_submitted_by_set_to_null_when_user_hard_deleted(self):
        """
        Staff member leaves → their user account is hard-deleted →
        expense record must survive with submitted_by=NULL.
        """
        expense = _Factory.expense(self.project, submitted_by=self.user)
        self.assertEqual(expense.submitted_by, self.user)

        # Hard delete the user (not soft delete — simulates Django admin delete)
        self.user.delete()

        expense.refresh_from_db()
        self.assertIsNone(expense.submitted_by)
        self.assertIsNotNone(expense.pk)   # expense still exists

    def test_expense_amount_unchanged_after_user_deleted(self):
        expense = _Factory.expense(
            self.project,
            submitted_by = self.user,
            amount       = Decimal("99999.99"),
        )
        self.user.delete()
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal("99999.99"))

    def test_expense_with_no_submitted_by_saves_fine(self):
        expense = _Factory.expense(self.project, submitted_by=None)
        expense.refresh_from_db()
        self.assertIsNone(expense.submitted_by)
        self.assertIsNotNone(expense.pk)