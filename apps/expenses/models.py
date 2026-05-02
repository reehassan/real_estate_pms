from django.conf import settings
from django.db import models


class Expense(models.Model):

    CATEGORY_CHOICES = [
        ('construction', 'Construction'),
        ('marketing', 'Marketing'),
        ('salaries', 'Staff Salaries'),
        ('utilities', 'Utilities'),
        ('legal', 'Legal'),
        ('miscellaneous', 'Miscellaneous'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]

    project = models.ForeignKey(
        'projects_and_plots.Project',
        on_delete=models.CASCADE,
        related_name='expenses',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    vendor_name = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    date = models.DateField()
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_expenses',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses',
    )

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.get_category_display()} — {self.project.name} — PKR {self.amount:,.0f}"