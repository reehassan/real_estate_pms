"""
apps/projects/models.py

Project and Plot models for Real Estate PMS.
Represents a housing scheme or development project.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

# MANAGERS
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# MODELS

# PROJECT
class Project(models.Model):

    class AreaUnit(models.TextChoices):
        MARLA = 'MARLA', 'Marla'
        KANAL = 'KANAL', 'Kanal'
        SQFT  = 'SQFT',  'Square Feet'

    class Status(models.TextChoices):
        PLANNING  = 'PLANNING',  'Planning'
        ACTIVE    = 'ACTIVE',    'Active'
        ON_HOLD   = 'ON_HOLD',   'On Hold'
        COMPLETED = 'COMPLETED', 'Completed'

    # FEILDS
    name          = models.CharField(max_length=100)
    location      = models.CharField(max_length=200)
    total_area    = models.PositiveIntegerField()
    area_unit     = models.CharField(max_length=10, choices=AreaUnit.choices, default=AreaUnit.MARLA)
    description   = models.TextField(null=True, blank=True)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNING)

    # SOFT DELETE
    is_deleted    = models.BooleanField(default=False)
    deleted_at    = models.DateTimeField(null=True, blank= True)

    # TIMESTAMPS
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    # MANAGERS
    objects     = SoftDeleteManager()   # default — excludes deleted records
    all_objects = models.Manager()      # use only in admin or recovery


    class Meta:
        verbose_name            = 'Project'
        verbose_name_plural     = 'Projects'
        ordering                =  ['-created_at']


    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


# PLOT 
class Plot(models.Model):

    class SizeUnit(models.TextChoices):
        MARLA = 'MARLA', 'Marla'
        KANAL = 'KANAL', 'Kanal'
        SQFT  = 'SQFT',  'Square Feet'

    class Category(models.TextChoices):
        RESIDENTIAL = 'RESIDENTIAL', 'Residential'
        COMMERCIAL  = 'COMMERCIAL',  'Commercial'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        BOOKED    = 'BOOKED',    'Booked'
        SOLD      = 'SOLD',      'Sold'

    # RELATIONS
    project     = models.ForeignKey(
                    Project,
                    on_delete=models.PROTECT,
                    related_name='plots'
                  )

    # IDENTIFICATION
    plot_number = models.CharField(max_length=20)
    block       = models.CharField(max_length=50, null=True, blank=True)

    # PHYSICAL DETAILS
    size        = models.DecimalField(
                    max_digits=10,
                    decimal_places=2,
                    validators=[MinValueValidator(0.01)]
                  )
    size_unit   = models.CharField(max_length=10, choices=SizeUnit.choices, default=SizeUnit.MARLA)
    category    = models.CharField(max_length=20, choices=Category.choices, default=Category.RESIDENTIAL)

    # FINANCIALS
    price       = models.DecimalField(
                    max_digits=15,
                    decimal_places=2,
                    validators=[MinValueValidator(0.01)]
                  )

    # STATUS
    status      = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE)
    notes       = models.TextField(null=True, blank=True)

    # SOFT DELETE
    is_deleted  = models.BooleanField(default=False)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    # TIMESTAMPS
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # MANAGERS
    objects     = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name        = 'Plot'
        verbose_name_plural = 'Plots'
        ordering            = ['project', 'block', 'plot_number']
        constraints         = [
            models.UniqueConstraint(
                fields=['project', 'plot_number'],
                name='unique_plot_per_project'
            )
        ]
        indexes             = [
            models.Index(fields=['status'], name='idx_plot_status')
        ]

    def __str__(self):
        return f'{self.project.name} — {self.block or ""} {self.plot_number}'.strip()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()