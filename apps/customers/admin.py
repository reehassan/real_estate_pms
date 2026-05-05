# apps/customers/admin.py

from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.html import format_html

from .models import Customer


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOM LIST FILTER FOR SOFT DELETE
# ──────────────────────────────────────────────────────────────────────────────

class DeletedFilter(admin.SimpleListFilter):
    title = _('deleted status')
    parameter_name = 'deleted'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('Show deleted only')),
            ('all', _('Show all (including deleted)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_deleted=True)
        if self.value() == 'all':
            return Customer.all_objects.all()
        # Default: exclude deleted customers
        return queryset.filter(is_deleted=False)


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOMER ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Professional admin configuration for Customer model.
    Soft‑deleted customers are hidden by default; use filter to show them.
    """
    list_display = (
        'full_name',
        'cnic',
        'phone',
        'customer_type',
        'created_at',
    )
    list_display_links = ('full_name', 'cnic')
    list_filter = ('customer_type', DeletedFilter, 'created_at')
    search_fields = ('cnic', 'full_name', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    ordering = ('-created_at',)

    fieldsets = (
        (_('Personal Information'), {
            'fields': ('full_name', 'cnic', 'phone', 'address', 'customer_type')
        }),
        (_('Soft Delete'), {
            'fields': ('deleted_at',),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['restore_selected']

    def get_queryset(self, request):
        """Default: exclude soft‑deleted customers."""
        return Customer.objects.all()  # uses SoftDeleteManager

    @admin.action(description=_('Restore selected customers'))
    def restore_selected(self, request, queryset):
        """Restore soft‑deleted customers."""
        updated = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_at=None)
        self.message_user(
            request,
            _('%(count)d customer(s) were restored.') % {'count': updated},
            messages.SUCCESS
        )

    def delete_model(self, request, obj):
        """Soft delete single customer."""
        obj.delete()  # calls model's delete() -> soft delete
        self.message_user(
            request,
            _('Customer “%(name)s” was soft‑deleted.') % {'name': obj.full_name},
            messages.WARNING
        )

    def delete_queryset(self, request, queryset):
        """Soft delete multiple customers."""
        for obj in queryset:
            obj.delete()
        self.message_user(
            request,
            _('Selected customers were soft‑deleted.'),
            messages.WARNING
        )