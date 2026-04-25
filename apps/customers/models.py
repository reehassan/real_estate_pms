"""
apps/customers/models.py

Customer model for Real Estate PMS.
Represents a person or entity that books or buys a plot.

"""

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


# ─────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────

cnic_validator = RegexValidator(
    regex=r'^\d{5}-\d{7}-\d{1}$',
    message='Enter a valid CNIC in format XXXXX-XXXXXXX-X.'
)

phone_validator = RegexValidator(
    regex=r'^\+?92\d{10}$|^0\d{10}$',
    message='Enter a valid Pakistani phone number e.g. 03001234567.'
)


# ─────────────────────────────────────────────
# MANAGERS
# ─────────────────────────────────────────────

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class Customer(models.Model):

    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', 'Individual'
        JOINT      = 'JOINT',      'Joint'
        CORPORATE  = 'CORPORATE',  'Corporate'

    # PERSONAL DETAILS
    full_name     = models.CharField(max_length=100)
    cnic          = models.CharField(
                        max_length=15,
                        unique=True,
                        validators=[cnic_validator],
                        help_text='Format: XXXXX-XXXXXXX-X'
                    )
    phone         = models.CharField(max_length=15, validators=[phone_validator])
    address       = models.TextField()
    customer_type = models.CharField(
                        max_length=15,
                        choices=CustomerType.choices,
                        default=CustomerType.INDIVIDUAL
                    )

    # SOFT DELETE
    is_deleted    = models.BooleanField(default=False)
    deleted_at    = models.DateTimeField(null=True, blank=True)

    # TIMESTAMPS
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    # MANAGERS
    objects       = SoftDeleteManager()
    all_objects   = models.Manager()

    class Meta:
        verbose_name        = 'Customer'
        verbose_name_plural = 'Customers'
        ordering            = ['full_name']
        indexes             = [
            models.Index(fields=['cnic'],      name='unique_customer_cnic'),
            models.Index(fields=['full_name'], name='idx_customer_name'),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.cnic})'

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()