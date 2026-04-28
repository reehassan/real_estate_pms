"""
apps/bookings/models.py

Booking and Installment models for Royal Land PMS.
Core business transaction — links a Customer to a Plot.

Out of scope:
    - Payment reversal / correction
    - Overpayment handling
    - Late fee automation
    - Status transition signals (handled in apps/bookings/signals.py)
    - Installment auto-generation signal (handled in apps/bookings/signals.py)
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
# MANAGERS
# ─────────────────────────────────────────────

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class Booking(models.Model):

    class PaymentPlan(models.TextChoices):
        LUMP_SUM    = 'lump',  'Lump Sum'
        THREE_YEAR  = '3yr',   'Three Year'
        FIVE_YEAR   = '5yr',   'Five Year'

    class Status(models.TextChoices):
        ACTIVE      = 'active',     'Active'
        COMPLETED   = 'completed',  'Completed'
        CANCELLED   = 'cancelled',  'Cancelled'

    # RELATIONS
    customer    = models.ForeignKey(
                    'customers.Customer',
                    on_delete=models.PROTECT,
                    related_name='bookings',
                  )
    plot        = models.ForeignKey(
                    'projects_and_plots.Plot',
                    on_delete=models.PROTECT,
                    related_name='bookings',
                  )
    booked_by   = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.SET_NULL,
                    null=True,
                    related_name='staff_created_bookings',
                  )

    # FIELDS
    booking_date    = models.DateField(default=timezone.localdate)
    total_price     = models.DecimalField(
                        max_digits=15,
                        decimal_places=2,
                        validators=[MinValueValidator(0.01)]
                      )
    down_payment    = models.DecimalField(
                        max_digits=15,
                        decimal_places=2,
                        validators=[MinValueValidator(0)]
                      )
    payment_plan    = models.CharField(
                        max_length=10,
                        choices=PaymentPlan.choices,
                      )
    status          = models.CharField(
                        max_length=15,
                        choices=Status.choices,
                        default=Status.ACTIVE,
                      )
    notes           = models.TextField(null=True, blank=True)

    # SOFT DELETE
    is_deleted      = models.BooleanField(default=False)
    deleted_at      = models.DateTimeField(null=True, blank=True)

    # TIMESTAMPS
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # MANAGERS
    objects         = SoftDeleteManager()
    all_objects     = models.Manager()

    def __str__(self):
        return f'{self.customer.full_name} — Plot {self.plot.plot_number}'

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    class Meta:
        verbose_name        = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering            = ['-created_at']
        constraints         = [
            models.UniqueConstraint(
                fields=['plot'],
                condition=models.Q(status='active'),
                name='unique_active_booking_per_plot'
            )
        ]
        indexes = [
            models.Index(fields=['status'],   name='idx_booking_status'),
            models.Index(fields=['customer'], name='idx_booking_customer'),
            models.Index(fields=['plot'],     name='idx_booking_plot'),
        ]


class Installment(models.Model):

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID    = 'paid',    'Paid'
        OVERDUE = 'overdue', 'Overdue'

    # RELATIONS
    booking             = models.ForeignKey(
                            Booking,
                            on_delete=models.CASCADE,
                            related_name='installments',
                          )

    # FIELDS
    challan_number      = models.CharField(max_length=30, unique=True)
    installment_number  = models.PositiveIntegerField()
    due_date            = models.DateField()
    amount_due          = models.DecimalField(
                            max_digits=15,
                            decimal_places=2,
                            validators=[MinValueValidator(0.01)]
                          )
    amount_paid         = models.DecimalField(
                            max_digits=15,
                            decimal_places=2,
                            default=0,
                            validators=[MinValueValidator(0)]
                          )
    paid_on             = models.DateField(null=True, blank=True)
    status              = models.CharField(
                            max_length=10,
                            choices=Status.choices,
                            default=Status.PENDING,
                          )
    notes               = models.TextField(null=True, blank=True)

    # TIMESTAMPS
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Installment'
        verbose_name_plural = 'Installments'
        ordering            = ['due_date', 'installment_number']
        constraints         = [
            models.UniqueConstraint(
                fields=['booking', 'installment_number'],
                name='unique_installment_per_booking'
            )
        ]
        indexes             = [
            models.Index(fields=['status'],   name='idx_installment_status'),
            models.Index(fields=['due_date'], name='idx_installment_due_date'),
        ]

    def __str__(self):
        return f'{self.challan_number} ({self.get_status_display()})'