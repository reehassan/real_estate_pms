"""
apps/accounts/admin.py
Production-ready admin for custom User model.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display
from simple_history.admin import SimpleHistoryAdmin

from .models import User


@admin.register(User)
class UserAdmin(UnfoldModelAdmin,SimpleHistoryAdmin, BaseUserAdmin):

    # ── List page ──────────────────────────────────────────────────
    list_display = (
        "username",
        "full_name",
        "email",
        "role_badge",
        "status_badge",
        "date_joined",
    )
    list_filter   = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering      = ("username",)
    list_per_page = 25

    # ── Detail page ────────────────────────────────────────────────
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        ("Account", {
            "fields": ("username", "password"),
        }),
        ("Personal Info", {
            "fields": (
                ("first_name", "last_name"),
                "email",
            ),
        }),
        ("Role & Access", {
            "fields": ("is_active", "is_staff", "is_superuser"),
            "description": (
                "Admin = is_superuser ON. "
                "Staff = is_staff ON, is_superuser OFF. "
                "Do not assign groups or individual permissions — "
                "roles are managed via these flags only."
            ),
        }),
        ("Record Info", {
            "fields": ("date_joined", "last_login"),
            "classes": ("collapse",),
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email",
                "first_name", "last_name",
                "password1", "password2",
                "is_staff", "is_superuser",
            ),
        }),
    )

    # ── Display methods ────────────────────────────────────────────

    @display(description=_("Full Name"))
    def full_name(self, obj):
        name = obj.get_full_name()
        return name if name.strip() else "—"

    @display(description=_("Role"), label={
        "Admin": "danger",
        "Staff": "primary",
        "User":  "secondary",
    })
    def role_badge(self, obj):
        if obj.is_superuser:
            return "Admin"
        if obj.is_staff:
            return "Staff"
        return "User"

    @display(description=_("Status"), label={
        "Active":   "success",
        "Inactive": "secondary",
    })
    def status_badge(self, obj):
        return "Active" if obj.is_active else "Inactive"
    

@admin.register(User.history.model)
class HistoricalUserAdmin(UnfoldModelAdmin):
    list_display  = ("username", "email", "is_active", "is_staff", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "is_active", "is_staff")
    search_fields = ("username", "email")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in User.history.model._meta.get_fields()]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False