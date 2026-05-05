# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django import forms

from .models import User


class CustomUserChangeForm(UserChangeForm):
    """Form for updating existing users – ensures email is required and unique."""
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users – enforces unique email and required fields.
    Password help text is simplified for a cleaner admin look.
    """
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_("Enter a strong password (min. 8 characters, not too common)."),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_("Enter the same password as above, for verification."),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Professional admin configuration for the custom User model.
    
    Inherits from Django's default UserAdmin but adapts fieldsets and forms
    to match our custom User model (email is unique & required, no phone/CNIC).
    """
    # Forms
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # List view configuration
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_active',
        'date_joined',
        'last_login',
    )
    list_display_links = ('username', 'email')
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'groups',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login')

    # Fieldsets for editing existing users
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            ),
        }),
        (_('Important dates'), {'fields': ('date_joined', 'last_login')}),
    )

    # Fieldsets for the "Add user" page (simpler, only essential fields)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'first_name',
                'last_name',
                'password1',
                'password2',
            ),
        }),
    )

    # Actions
    actions = ['activate_users', 'deactivate_users']

    @admin.action(description=_('Activate selected users'))
    def activate_users(self, request, queryset):
        """Bulk activate users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, _('%(count)d users were successfully activated.') % {'count': updated})

    @admin.action(description=_('Deactivate selected users'))
    def deactivate_users(self, request, queryset):
        """Bulk deactivate users (soft disable)."""
        updated = queryset.update(is_active=False)
        self.message_user(request, _('%(count)d users were successfully deactivated.') % {'count': updated})

    # Optional: override save_model to enforce any business rules (e.g., email normalization)
    def save_model(self, request, obj, form, change):
        """Normalize email to lowercase before saving."""
        if obj.email:
            obj.email = obj.email.lower()
        super().save_model(request, obj, form, change)

    # Improve performance for large user lists
    def get_queryset(self, request):
        """Prefetch groups to reduce query count."""
        return super().get_queryset(request).prefetch_related('groups')