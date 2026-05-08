"""
apps/customers/tests.py

Test suite for the Customer domain — model, validators, soft delete, managers.

Coverage:
    CustomerModelTests        — fields, __str__, defaults, soft delete, managers
    CustomerValidatorTests    — CNIC and phone regex validators
    CustomerTypeTests         — CustomerType choices and default
    CustomerSoftDeleteTests   — delete() behaviour, timestamps, manager filtering
    CustomerUniqueConstraints — CNIC uniqueness at DB level

Run:
    python manage.py test apps.customers.tests --verbosity=2
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone


from .models import Customer


# ─────────────────────────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────────────────────────

class _Factory:
    _counter = 0

    @classmethod
    def customer(cls, **kwargs) -> Customer:
        cls._counter += 1
        n = cls._counter
        defaults = dict(
            full_name     = f"Test Customer {n}",
            cnic          = f"35202-{n:07d}-1",
            phone         = f"0300{n:07d}"[:11],
            address       = "123 Test Street, Rawalpindi",
            customer_type = Customer.CustomerType.INDIVIDUAL,
        )
        defaults.update(kwargs)
        return Customer.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────
# 1. CUSTOMER MODEL TESTS
# ─────────────────────────────────────────────────────────────────

class CustomerModelTests(TestCase):

    def setUp(self):
        self.customer = _Factory.customer(
            full_name     = "Ahmed Khan",
            cnic          = "35202-1234567-1",
            phone         = "03001234567",
            address       = "House 5, Street 3, Rawalpindi",
            customer_type = Customer.CustomerType.INDIVIDUAL,
        )

    # ── __str__ ───────────────────────────────────────────────────

    def test_str_contains_full_name(self):
        self.assertIn("Ahmed Khan", str(self.customer))

    def test_str_contains_cnic(self):
        self.assertIn("35202-1234567-1", str(self.customer))

    def test_str_format_is_name_then_cnic_in_parens(self):
        self.assertEqual(str(self.customer), "Ahmed Khan (35202-1234567-1)")

    # ── Defaults ──────────────────────────────────────────────────

    def test_is_deleted_defaults_to_false(self):
        self.assertFalse(self.customer.is_deleted)

    def test_deleted_at_defaults_to_none(self):
        self.assertIsNone(self.customer.deleted_at)

    def test_customer_type_defaults_to_individual(self):
        c = Customer.objects.create(
            full_name = "Default Type",
            cnic      = "35202-9999991-1",
            phone     = "03009999991",
            address   = "Test",
        )
        self.assertEqual(c.customer_type, Customer.CustomerType.INDIVIDUAL)

    # ── Timestamps ────────────────────────────────────────────────

    def test_created_at_is_set_on_creation(self):
        self.assertIsNotNone(self.customer.created_at)

    def test_updated_at_is_set_on_creation(self):
        self.assertIsNotNone(self.customer.updated_at)

    def test_updated_at_changes_on_save(self):
        before = self.customer.updated_at
        self.customer.address = "New Address"
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertGreaterEqual(self.customer.updated_at, before)


# ─────────────────────────────────────────────────────────────────
# 2. VALIDATOR TESTS
# ─────────────────────────────────────────────────────────────────

class CustomerValidatorTests(TestCase):
    """
    Validators are run via full_clean() — Django does NOT call them
    on .save() or .objects.create() automatically.
    We test the validator objects directly for speed and clarity.
    """

    # ── CNIC validator ────────────────────────────────────────────

    def _valid_cnic(self, value: str):
        c = Customer(
            full_name = "Test",
            cnic      = value,
            phone     = "03001234567",
            address   = "Test",
        )
        c.full_clean()   # should not raise

    def _invalid_cnic(self, value: str):
        c = Customer(
            full_name = "Test",
            cnic      = value,
            phone     = "03001234567",
            address   = "Test",
        )
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_valid_cnic_standard_format(self):
        self._valid_cnic("35202-1234567-1")

    def test_valid_cnic_all_zeros(self):
        self._valid_cnic("00000-0000000-0")

    def test_invalid_cnic_no_dashes(self):
        self._invalid_cnic("3520212345671")

    def test_invalid_cnic_wrong_segment_lengths(self):
        # First segment must be 5 digits
        self._invalid_cnic("3520-1234567-1")

    def test_invalid_cnic_letters_in_number(self):
        self._invalid_cnic("3520A-1234567-1")

    def test_invalid_cnic_missing_last_digit(self):
        self._invalid_cnic("35202-1234567-")

    def test_invalid_cnic_extra_digits(self):
        self._invalid_cnic("352021-1234567-1")

    def test_invalid_cnic_empty_string(self):
        self._invalid_cnic("")

    # ── Phone validator ───────────────────────────────────────────

    def _valid_phone(self, value: str):
        c = Customer(
            full_name = "Test",
            cnic      = "35202-0000001-1",
            phone     = value,
            address   = "Test",
        )
        c.full_clean()

    def _invalid_phone(self, value: str):
        c = Customer(
            full_name = "Test",
            cnic      = "35202-0000001-1",
            phone     = value,
            address   = "Test",
        )
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_valid_phone_local_format(self):
        self._valid_phone("03001234567")

    def test_valid_phone_with_plus92(self):
        self._valid_phone("+923001234567")

    def test_valid_phone_with_92_no_plus(self):
        # regex: ^\+?92\d{10}$ matches 921234567890 (92 + 10 digits)
        self._valid_phone("921234567890")

    def test_invalid_phone_too_short(self):
        self._invalid_phone("0300123456")    # 10 digits — one short

    def test_invalid_phone_letters(self):
        self._invalid_phone("0300ABCDEFG")

    def test_invalid_phone_uk_format(self):
        self._invalid_phone("+441234567890")

    def test_invalid_phone_empty(self):
        self._invalid_phone("")

    def test_invalid_phone_starts_with_04(self):
        # Must start with 03 or +92/92
        self._invalid_phone("04001234567")


# ─────────────────────────────────────────────────────────────────
# 3. CUSTOMER TYPE TESTS
# ─────────────────────────────────────────────────────────────────

class CustomerTypeTests(TestCase):

    def test_individual_type_saves_and_retrieves(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.INDIVIDUAL)
        c.refresh_from_db()
        self.assertEqual(c.customer_type, Customer.CustomerType.INDIVIDUAL)

    def test_joint_type_saves_and_retrieves(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.JOINT)
        c.refresh_from_db()
        self.assertEqual(c.customer_type, Customer.CustomerType.JOINT)

    def test_corporate_type_saves_and_retrieves(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.CORPORATE)
        c.refresh_from_db()
        self.assertEqual(c.customer_type, Customer.CustomerType.CORPORATE)

    def test_get_customer_type_display_individual(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.INDIVIDUAL)
        self.assertEqual(c.get_customer_type_display(), "Individual")

    def test_get_customer_type_display_joint(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.JOINT)
        self.assertEqual(c.get_customer_type_display(), "Joint")

    def test_get_customer_type_display_corporate(self):
        c = _Factory.customer(customer_type=Customer.CustomerType.CORPORATE)
        self.assertEqual(c.get_customer_type_display(), "Corporate")


# ─────────────────────────────────────────────────────────────────
# 4. SOFT DELETE TESTS
# ─────────────────────────────────────────────────────────────────

class CustomerSoftDeleteTests(TestCase):

    def setUp(self):
        self.customer = _Factory.customer()

    # ── delete() sets correct fields ──────────────────────────────

    def test_delete_sets_is_deleted_to_true(self):
        self.customer.delete()
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_deleted)

    def test_delete_sets_deleted_at_timestamp(self):
        before = timezone.now()
        self.customer.delete()
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.deleted_at)
        self.assertGreaterEqual(self.customer.deleted_at, before)

    def test_delete_does_not_remove_row_from_database(self):
        pk = self.customer.pk
        self.customer.delete()
        # Row still exists — soft delete only
        self.assertTrue(Customer.all_objects.filter(pk=pk).exists())

    def test_delete_does_not_change_full_name(self):
        name = self.customer.full_name
        self.customer.delete()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, name)

    def test_delete_idempotent_second_call_does_not_raise(self):
        self.customer.delete()
        try:
            self.customer.delete()
        except Exception as e:
            self.fail(f"Second delete() raised unexpectedly: {e}")

    # ── Manager filtering after delete ────────────────────────────

    def test_default_manager_excludes_deleted_customer(self):
        pk = self.customer.pk
        self.customer.delete()
        self.assertFalse(Customer.objects.filter(pk=pk).exists())

    def test_all_objects_manager_includes_deleted_customer(self):
        pk = self.customer.pk
        self.customer.delete()
        self.assertTrue(Customer.all_objects.filter(pk=pk).exists())

    def test_default_manager_still_returns_non_deleted_customers(self):
        c2 = _Factory.customer()
        self.customer.delete()
        pks = list(Customer.objects.values_list("pk", flat=True))
        self.assertNotIn(self.customer.pk, pks)
        self.assertIn(c2.pk, pks)

    def test_all_objects_count_equals_total_including_deleted(self):
        c2 = _Factory.customer()
        self.customer.delete()
        self.assertEqual(Customer.all_objects.count(), 2)
        self.assertEqual(Customer.objects.count(), 1)

    # ── Re-using CNIC after soft delete ───────────────────────────

    def test_soft_deleted_customer_cnic_still_blocks_new_customer(self):
        """
        CNIC has a DB-level unique constraint. A soft-deleted customer
        still holds the CNIC at the DB row level — a new customer with
        the same CNIC must raise IntegrityError.
        This is intentional: CNICs are unique identifiers and should
        never be reassigned, even after soft deletion.
        """
        cnic = self.customer.cnic
        self.customer.delete()

        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                full_name = "Another Person",
                cnic      = cnic,
                phone     = "03009876543",
                address   = "Different Address",
            )


# ─────────────────────────────────────────────────────────────────
# 5. UNIQUE CONSTRAINT TESTS
# ─────────────────────────────────────────────────────────────────

class CustomerUniqueConstraintTests(TestCase):

    def test_duplicate_cnic_raises_integrity_error(self):
        _Factory.customer(cnic="35202-7654321-9")
        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                full_name = "Different Name",
                cnic      = "35202-7654321-9",   # same CNIC
                phone     = "03001111111",
                address   = "Different Address",
            )

    def test_different_cnics_both_save_successfully(self):
        c1 = _Factory.customer(cnic="35202-1111111-1")
        c2 = _Factory.customer(cnic="35202-2222222-2")
        self.assertIsNotNone(c1.pk)
        self.assertIsNotNone(c2.pk)

    def test_same_full_name_different_cnic_is_allowed(self):
        """Two people can share a name — only CNIC must be unique."""
        c1 = _Factory.customer(full_name="Ali Khan", cnic="35202-1111111-1")
        c2 = _Factory.customer(full_name="Ali Khan", cnic="35202-2222222-2")
        self.assertIsNotNone(c1.pk)
        self.assertIsNotNone(c2.pk)

    def test_same_phone_different_cnic_is_allowed(self):
        """Phone has no unique constraint — shared family phones are valid."""
        c1 = _Factory.customer(phone="03001234567", cnic="35202-1111111-1")
        c2 = _Factory.customer(phone="03001234567", cnic="35202-2222222-2")
        self.assertIsNotNone(c1.pk)
        self.assertIsNotNone(c2.pk)