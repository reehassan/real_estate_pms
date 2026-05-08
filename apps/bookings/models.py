"""
apps/bookings/models.py

Models:
    - Booking         : Links customer + plot, tracks token → down payment → installments
    - Installment     : Individual payment schedule entries with soft delete
    - BookingDocument : File attachments per booking (CNIC, agreements, receipts)

Booking status flow:
    TOKEN → ACTIVE → COMPLETED
                   ↘ CANCELLED (from any stage)

Plot status is updated via signals (apps/bookings/signals.py):
    Booking TOKEN    → Plot TOKEN
    Booking ACTIVE   → Plot BOOKED
    Booking COMPLETED → Plot SOLD
    Booking CANCELLED → Plot AVAILABLE

Out of scope:
    - Payment reversal / correction
    - Overpayment handling
    - Late fee automation
    - Status transition signals  → apps/bookings/signals.py
    - Installment auto-generation → apps/bookings/signals.py
    - Co-ownership / joint booking details
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
# BOOKING
# ─────────────────────────────────────────────

class Booking(models.Model):

    class PaymentPlan(models.TextChoices):
        LUMP_SUM   = 'LUMP',  'Lump Sum'
        SIX_MONTHS =  '6M' ,   '6 Months'
        ONE_YEAR   = '1YR',    'One Year'
        TWO_YEAR   = '2YR',    'Two Year'
        THREE_YEAR = '3YR',   'Three Year'
        FIVE_YEAR  = '5YR',   'Five Year'

    class Status(models.TextChoices):
        TOKEN     = 'TOKEN',     'Token'      # Token received, down payment pending
        ACTIVE    = 'ACTIVE',    'Active'     # Down payment received, installments running
        COMPLETED = 'COMPLETED', 'Completed'  # All installments paid
        CANCELLED = 'CANCELLED', 'Cancelled'  # Booking cancelled at any stage

    # ── Relations ──────────────────────────────────────────────────
    customer  = models.ForeignKey(
                    'customers.Customer',
                    on_delete=models.PROTECT,
                    related_name='bookings',
                )
    plot      = models.ForeignKey(
                    'projects_and_plots.Plot',
                    on_delete=models.PROTECT,
                    related_name='bookings',
                )
    booked_by = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.SET_NULL,
                    null=True,
                    related_name='staff_created_bookings',
                )

    # ── Core fields ────────────────────────────────────────────────
    booking_date = models.DateField(
                       default=timezone.localdate,
                       help_text="Date the booking was registered.",
                   )
    payment_plan = models.CharField(max_length=10, choices=PaymentPlan.choices)
    status       = models.CharField(
                       max_length=15,
                       choices=Status.choices,
                       default=Status.TOKEN,
                       help_text=(
                           "TOKEN → token received, awaiting down payment. "
                           "ACTIVE → down payment collected, installments running. "
                           "COMPLETED → all payments received. "
                           "CANCELLED → booking void."
                       ),
                   )
    total_price  = models.DecimalField(
                       max_digits=15,
                       decimal_places=2,
                       validators=[MinValueValidator(0.01)],
                       help_text="Agreed total sale price of the plot.",
                   )

    # ── Token stage ────────────────────────────────────────────────
    token_amount      = models.DecimalField(
                            max_digits=15,
                            decimal_places=2,
                            default=0,
                            validators=[MinValueValidator(0)],
                            help_text=(
                                "Amount received as token to hold the plot. "
                                "Appears on the token challan. "
                                "May be zero for direct bookings."
                            ),
                        )
    token_received_on = models.DateField(
                            null=True,
                            blank=True,
                            help_text="Date token payment was physically received.",
                        )

    # ── Down payment stage ─────────────────────────────────────────
    down_payment             = models.DecimalField(
                                   max_digits=15,
                                   decimal_places=2,
                                   validators=[MinValueValidator(0)],
                                   help_text=(
                                       "Down payment amount (excluding token). "
                                       "Total upfront = token_amount + down_payment."
                                   ),
                               )
    down_payment_received_on = models.DateField(
                                   null=True,
                                   blank=True,
                                   help_text=(
                                       "Date down payment was collected. "
                                       "Set this when payment is received — "
                                       "triggers status change to ACTIVE."
                                   ),
                               )

    notes = models.TextField(null=True, blank=True)

    # ── Soft delete ────────────────────────────────────────────────
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    # ── History ────────────────────────────────────────────────────
    history = HistoricalRecords()

    # ── Managers ───────────────────────────────────────────────────
    objects     = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name        = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering            = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['plot'],
                condition=models.Q(status__in=['TOKEN', 'ACTIVE']) & models.Q(is_deleted=False),
                name='unique_active_booking_per_plot',
            )
        ]
        indexes = [
            models.Index(fields=['status'],   name='idx_booking_status'),
            models.Index(fields=['customer'], name='idx_booking_customer'),
            models.Index(fields=['plot'],     name='idx_booking_plot'),
        ]

    def __str__(self):
        return f'{self.customer.full_name} — Plot {self.plot.plot_number}'

    # ── Computed properties ────────────────────────────────────────

    @property
    def total_upfront(self):
        """Token + down payment — total amount due before installments."""
        return self.token_amount + self.down_payment

    @property
    def installment_principal(self):
        """Amount to be spread across installments."""
        return self.total_price - self.total_upfront

    def delete(self, *args, **kwargs):
        """
        Soft delete: marks deleted AND cancels so the UniqueConstraint
        releases the plot for a new booking.
        Hard delete is intentionally not exposed via admin.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.status     = self.Status.CANCELLED
        self.save(update_fields=['is_deleted', 'deleted_at', 'status', 'updated_at'])


# ─────────────────────────────────────────────
# INSTALLMENT
# ─────────────────────────────────────────────

class Installment(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID    = 'PAID',    'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        WAIVED  = 'WAIVED',  'Waived'   # exceptional write-off

    # ── Relations ──────────────────────────────────────────────────
    booking = models.ForeignKey(
                  Booking,
                  on_delete=models.CASCADE,
                  related_name='installments',
              )

    # ── Fields ─────────────────────────────────────────────────────
    challan_number     = models.CharField(
                             max_length=30,
                             unique=True,
                             help_text="System-generated challan reference number.",
                         )
    installment_number = models.PositiveIntegerField(
                             help_text="Sequential number within this booking (1, 2, 3 …).",
                         )
    due_date           = models.DateField()
    amount_due         = models.DecimalField(
                             max_digits=15,
                             decimal_places=2,
                             validators=[MinValueValidator(0.01)],
                         )
    amount_paid        = models.DecimalField(
                             max_digits=15,
                             decimal_places=2,
                             default=0,
                             validators=[MinValueValidator(0)],
                         )
    paid_on            = models.DateField(
                             null=True,
                             blank=True,
                             help_text="Date payment was physically received.",
                         )
    status             = models.CharField(
                             max_length=10,
                             choices=Status.choices,
                             default=Status.PENDING,
                         )
    notes              = models.TextField(null=True, blank=True)

    # ── Soft delete ────────────────────────────────────────────────
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    # ── History ────────────────────────────────────────────────────
    history = HistoricalRecords()

    # ── Managers ───────────────────────────────────────────────────
    objects     = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name        = 'Installment'
        verbose_name_plural = 'Installments'
        ordering            = ['due_date', 'installment_number']
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'installment_number'],
                name='unique_installment_per_booking',
            )
        ]
        indexes = [
            models.Index(fields=['status'],   name='idx_installment_status'),
            models.Index(fields=['due_date'], name='idx_installment_due_date'),
        ]

    def __str__(self):
        return f'{self.challan_number} ({self.get_status_display()})'

    # ── Computed properties ────────────────────────────────────────

    @property
    def balance(self):
        """Amount still owed on this installment."""
        return self.amount_due - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.amount_paid >= self.amount_due

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])


# ─────────────────────────────────────────────
# BOOKING DOCUMENT
# ─────────────────────────────────────────────

class BookingDocument(models.Model):

    class DocType(models.TextChoices):
        CNIC             = 'CNIC',             'CNIC Copy'
        TOKEN_RECEIPT    = 'TOKEN_RECEIPT',    'Token Receipt'
        SALE_AGREEMENT   = 'SALE_AGREEMENT',   'Sale Agreement'
        ALLOTMENT_LETTER = 'ALLOTMENT_LETTER', 'Allotment Letter'
        PAYMENT_RECEIPT  = 'PAYMENT_RECEIPT',  'Payment Receipt'
        OTHER            = 'OTHER',            'Other'

    # ── Relations ──────────────────────────────────────────────────
    booking     = models.ForeignKey(
                      Booking,
                      on_delete=models.CASCADE,
                      related_name='documents',
                  )
    uploaded_by = models.ForeignKey(
                      settings.AUTH_USER_MODEL,
                      on_delete=models.SET_NULL,
                      null=True,
                      related_name='uploaded_booking_docs',
                  )

    # ── Fields ─────────────────────────────────────────────────────
    doc_type    = models.CharField(
                      max_length=20,
                      choices=DocType.choices,
                      help_text="Type of document being uploaded.",
                  )
    file        = models.FileField(
                      upload_to='bookings/documents/%Y/%m/',
                      help_text="PDF, image, or scanned document.",
                  )
    notes       = models.TextField(
                      blank=True,
                      null=True,
                      help_text="Optional note about this document.",
                  )

    # ── Timestamps ─────────────────────────────────────────────────
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Booking Document'
        verbose_name_plural = 'Booking Documents'
        ordering            = ['uploaded_at']

    def __str__(self):
        return f'{self.get_doc_type_display()} — {self.booking}'