"""
apps/expenses/models.py

Expense model for Royal Land PMS.
Tracks all project expenditure. Staff logs expenses after completion.
Optional document upload (receipt, invoice, cheque scan).

Out of scope:
    - Approval workflow (cut from v1)
    - Email notifications
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


# ─────────────────────────────────────────────
# MANAGERS
# ─────────────────────────────────────────────

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class Expense(models.Model):

    class Category(models.TextChoices):
        # ── Tier 1 — happens on every project, every month ────────
        CONSTRUCTION     = 'construction',     'Construction'
        DAILY_LABOUR     = 'daily_labour',     'Daily Labour'
        SALARIES         = 'salaries',         'Staff Salaries'
        TRANSPORTATION   = 'transportation',   'Transportation & Fuel'

        # ── Tier 2 — happens frequently ───────────────────────────
        GOVERNMENT_FEES  = 'government_fees',  'Government Fees & NOC'
        COMMISSION       = 'commission',       'Agent Commission'
        MARKETING        = 'marketing',        'Marketing & Advertising'
        UTILITIES        = 'utilities',        'Utilities'

        # ── Tier 3 — happens occasionally ─────────────────────────
        EQUIPMENT_RENTAL = 'equipment_rental', 'Equipment Rental'
        MAINTENANCE      = 'maintenance',      'Maintenance & Repair'
        OFFICE_SUPPLIES  = 'office_supplies',  'Office Supplies'
        FOOD             = 'food',             'Food'
        RENT             = 'rent',             'Office / Site Rent'
        SECURITY         = 'security',         'Security'
        LEGAL            = 'legal',            'Legal & Documentation'

        # ── Tier 4 — rare but needs tracking ──────────────────────
        INSURANCE        = 'insurance',        'Insurance'
        TAXES            = 'taxes',            'Taxes & Duties'
        MISCELLANEOUS    = 'miscellaneous',    'Miscellaneous'

    class PaymentMethod(models.TextChoices):
        CASH     = 'cash',     'Cash'
        TRANSFER = 'transfer', 'Bank Transfer'
        CHEQUE   = 'cheque',   'Cheque'
        ONLINE   = 'online',   'Online'

    # RELATIONS
    project      = models.ForeignKey(
                     'projects_and_plots.Project',
                     on_delete=models.CASCADE,
                     related_name='expenses',
                   )
    submitted_by = models.ForeignKey(
                     settings.AUTH_USER_MODEL,
                     on_delete=models.SET_NULL,
                     null=True,
                     related_name='submitted_expenses',
                   )

    # FIELDS
    category         = models.CharField(max_length=20, choices=Category.choices)
    amount           = models.DecimalField(
                         max_digits=15,
                         decimal_places=2,
                         validators=[MinValueValidator(0.01)]
                       )
    vendor_name      = models.CharField(max_length=100, blank=True)
    description      = models.TextField()
    date             = models.DateField()
    payment_method   = models.CharField(max_length=10, choices=PaymentMethod.choices)
    reference_number = models.CharField(max_length=100, blank=True)
    document         = models.FileField(
                         upload_to='expenses/documents/%Y/%m/',
                         null=True,
                         blank=True,
                         help_text='Optional — receipt, invoice, or cheque scan'
                       )

    # SOFT DELETE
    is_deleted  = models.BooleanField(default=False)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    # TIMESTAMPS
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # HISTORY
    history = HistoricalRecords()

    # MANAGERS
    objects     = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name        = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['project'],  name='idx_expense_project'),
            models.Index(fields=['category'], name='idx_expense_category'),
            models.Index(fields=['date'],     name='idx_expense_date'),
        ]

    def __str__(self):
        return f'{self.get_category_display()} — {self.project.name} — PKR {self.amount:,.0f}'

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()