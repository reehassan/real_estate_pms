"""
apps/accounts/admin.py

Production-ready admin for custom User model + Django Group management.

Changes vs previous version:
    - GroupAdmin registered with Unfold styling
    - Groups added to User fieldsets (so you can assign staff to groups)
    - user_permissions removed from fieldsets (manage via groups, not per-user)
    - Role & Access description updated to reflect group-based workflow
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display
from simple_history.admin import SimpleHistoryAdmin

from .models import User


# ─────────────────────────────────────────────
# GROUP ADMIN
# ─────────────────────────────────────────────

# Unregister Django's default plain Group admin first
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(UnfoldModelAdmin):
    """
    Styled Group management with Unfold.
    Use this to create permission groups:
        - Sales Staff
        - Accounts Staff
        - Manager
    Then assign staff users to these groups in the User admin below.
    """
    search_fields = ("name",)
    ordering      = ("name",)
    list_display  = ("name", "member_count")
    list_per_page = 25

    # Show permissions as a filtered horizontal widget
    filter_horizontal = ("permissions",)

    fieldsets = (
        (None, {
            "fields": ("name",),
        }),
        (_("Permissions"), {
            "fields": ("permissions",),
            "description": (
                "Select the specific admin permissions this group grants. "
                "Users assigned to this group will inherit all these permissions."
            ),
            "classes": ("wide",),
        }),
    )

    @display(description=_("Members"))
    def member_count(self, obj):
        count = obj.user_set.count()
        return f"{count} user{'s' if count != 1 else ''}"


# ─────────────────────────────────────────────
# USER ADMIN
# ─────────────────────────────────────────────

@admin.register(User)
class UserAdmin(UnfoldModelAdmin, SimpleHistoryAdmin, BaseUserAdmin):

    # ── List page ──────────────────────────────────────────────────
    list_display = (
        "username",
        "full_name",
        "email",
        "role_badge",
        "status_badge",
        "group_list",
        "date_joined",
    )
    list_filter   = ("is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering      = ("username",)
    list_per_page = 25

    # ── Detail page ────────────────────────────────────────────────
    readonly_fields  = ("date_joined", "last_login")
    filter_horizontal = ("groups",)   # nice double-list widget for group assignment

    fieldsets = (
        (_("Account"), {
            "fields": ("username", "password"),
        }),
        (_("Personal Info"), {
            "fields": (
                ("first_name", "last_name"),
                "email",
            ),
        }),
        (_("Role & Access"), {
            "fields": ("is_active", "is_staff", "is_superuser"),
            "description": (
                "Admin = is_superuser ON (full access, sees everything). "
                "Staff = is_staff ON, is_superuser OFF (access controlled by Groups below). "
                "Inactive = user cannot log in."
            ),
        }),
        (_("Permission Groups"), {
            "fields": ("groups",),
            "description": (
                "Assign this user to one or more groups to grant permissions. "
                "Create groups under Users & Auth → Permission Groups in the sidebar. "
                "Recommended groups: Sales Staff, Accounts Staff, Manager."
            ),
            "classes": ("wide",),
        }),
        (_("Record Info"), {
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
                "groups",
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

    @display(description=_("Groups"))
    def group_list(self, obj):
        groups = obj.groups.values_list("name", flat=True)
        return ", ".join(groups) if groups else "—"


# ─────────────────────────────────────────────
# HISTORICAL USER ADMIN
# ─────────────────────────────────────────────

@admin.register(User.history.model)
class HistoricalUserAdmin(UnfoldModelAdmin):
    list_display  = (
        "username", "email", "is_active", "is_staff",
        "history_date", "history_type", "history_user",
    )
    list_filter   = ("history_type", "is_active", "is_staff")
    search_fields = ("username", "email")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in User.history.model._meta.get_fields()]

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False