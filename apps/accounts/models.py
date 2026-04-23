"""
accounts/models.py

Custom User model for the Property Management System.

Extends Django's AbstractUser to add Pakistan-specific fields (CNIC, phone)
and enforces a unique email constraint. Authentication and role management
rely entirely on Django's built-in permission system:
    - Admin  → is_superuser = True
    - Staff  → is_staff = True, is_superuser = False
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


# ─────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message='Enter a valid phone number. Up to 15 digits, optional + prefix.'
)

cnic_validator = RegexValidator(
    regex=r'^\d{5}-\d{7}-\d{1}$',
    message='Enter a valid Pakistani CNIC in format XXXXX-XXXXXXX-X.'
)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class User(AbstractUser):
    email = models.EmailField(unique=True, blank=False)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    cnic  = models.CharField(max_length=15, unique=True, null=True, blank=True, validators=[cnic_validator])

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.get_full_name()} ({self.username})'