"""
apps/expenses/admin.py

Production-grade Unfold admin for Expense model.

Features:
    - Unfold label={} badges on category and payment method
    - Import / Export (CSV + XLSX)
    - Date-range filter on date and created_at
    - Running total annotation shown in list
    - Auto-sets submitted_by on create
    - Document preview link
    - Soft-delete aware
    - Dark-mode safe throughout
"""

from django.contrib import admin
from django.db.models import Sum
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from apps.expenses.models import Expense

from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from rangefilter.filters import DateRangeFilterBuilder

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display

from simple_history.admin import SimpleHistoryAdmin

from .models import Expense


# ─────────────────────────────────────────────
# RESOURCE
# ─────────────────────────────────────────────

class ExpenseResource(resources.ModelResource):
    project_name     = fields.Field(column_name="Project")
    submitted_by_email = fields.Field(column_name="Submitted By")

    class Meta:
        model           = Expense
        skip_unchanged  = True
        report_skipped  = False
        fields = (
            "id", "date", "project_name", "category",
            "vendor_name", "description", "amount",
            "payment_method", "reference_number",
            "submitted_by_email", "created_at",
        )
        export_order = fields

    def dehydrate_project_name(self, obj):
        return obj.project.name if obj.project_id else ""

    def dehydrate_submitted_by_email(self, obj):
        return obj.submitted_by.email if obj.submitted_by_id else ""


# ─────────────────────────────────────────────
# BULK ACTIONS
# ─────────────────────────────────────────────

@admin.action(description="💳  Reassign selected to Miscellaneous")
def mark_miscellaneous(modeladmin, request, queryset):
    updated = queryset.update(category="miscellaneous")
    modeladmin.message_user(request, f"{updated} expense(s) reassigned.")


# ─────────────────────────────────────────────
# EXPENSE ADMIN
# ─────────────────────────────────────────────

@admin.register(Expense)
class ExpenseAdmin(ImportExportModelAdmin,  SimpleHistoryAdmin, UnfoldModelAdmin):
    resource_classes = [ExpenseResource]

    # ── Unfold UI ──────────────────────────────────────────────────
    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    # ── List view ──────────────────────────────────────────────────
    list_display = (
        "date",
        "project",
        "category_badge",
        "vendor_name",
        "amount_display",
        "payment_method_badge",
        "submitted_by",
    )
    list_filter = (
        "category",
        "payment_method",
        "project",
        ("date",       DateRangeFilterBuilder(title="Expense Date")),
        ("created_at", DateRangeFilterBuilder(title="Created")),
    )
    search_fields = (
        "vendor_name",
        "description",
        "reference_number",
        "project__name",
        "submitted_by__email",
        "submitted_by__username",
    )
    ordering           = ("-date",)
    date_hierarchy     = "date"
    list_per_page      = 25
    list_select_related = ("project", "submitted_by")
    actions            = [mark_miscellaneous]

    # ── Change form ────────────────────────────────────────────────
    readonly_fields = (
        "submitted_by", "created_at", "updated_at", "document_preview",
    )

    fieldsets = (
        (
            _("Expense Details"),
            {
                "fields": (
                    ("project", "category"),
                    ("amount", "date"),
                    "vendor_name",
                    "description",
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Payment"),
            {
                "fields": (("payment_method", "reference_number"),),
                "classes": ["wide"],
            },
        ),
        (
            _("Document"),
            {
                "fields": ("document", "document_preview"),
                "classes": ["wide"],
                "description": "Upload a receipt, invoice, or cheque scan (optional).",
            },
        ),
        (
            _("Record Info"),
            {
                "fields": ("submitted_by", "created_at", "updated_at"),
                "classes": ["collapse"],
            },
        ),
    )

    # ── Queryset ───────────────────────────────────────────────────

    def get_queryset(self, request):
        return (
            Expense.objects
            .filter(is_deleted=False)
            .select_related("project", "submitted_by")
        )

    # ── Auto-set submitted_by ──────────────────────────────────────

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.submitted_by = request.user
        super().save_model(request, obj, form, change)

    # ── Running total injected into changelist context ─────────────

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            qs    = response.context_data["cl"].queryset
            total = qs.aggregate(total=Sum("amount"))["total"] or 0
            count = qs.count()
            # Inject as a visible info banner below the filters
            response.context_data["expense_summary"] = mark_safe(
                f'<div style="display:inline-flex;align-items:center;gap:12px;'
                f'background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #7c3aed;'
                f'border-radius:6px;padding:10px 18px;margin-bottom:12px;font-size:13px;">'
                f'<span style="color:#64748b;">'
                f'{count} expense{"s" if count != 1 else ""} in current filter</span>'
                f'<span style="font-weight:700;color:#7c3aed;font-size:15px;">'
                f'₨ {total:,.0f}</span>'
                f'</div>'
            )
        except (AttributeError, KeyError):
            pass
        return response

    # ── Badges ─────────────────────────────────────────────────────
    @display(
        description=_("Category"),
        ordering="category",
        label={
            # Tier 1 — violet/primary for high-cost items
            "Construction":          "primary",
            "Daily Labour":          "primary",
            "Staff Salaries":        "success",
            "Transportation & Fuel": "info",
 
            # Tier 2
            "Government Fees & NOC": "warning",
            "Agent Commission":      "warning",
            "Marketing & Advertising": "info",
            "Utilities":             "warning",
 
            # Tier 3
            "Equipment Rental":      "info",
            "Maintenance & Repair":  "secondary",
            "Office Supplies":       "secondary",
            "Food":  "success",
            "Office / Site Rent":    "secondary",
            "Security":              "secondary",
            "Legal & Documentation": "warning",
 
            # Tier 4
            "Insurance":             "secondary",
            "Taxes & Duties":        "danger",
            "Miscellaneous":         "secondary",
        },
    )
    
    def category_badge(self, obj):
        return obj.get_category_display()


    @display(
        description=_("Payment"),
        ordering="payment_method",
        label={
            "Cash":          "success",
            "Bank Transfer": "primary",
            "Cheque":        "info",
            "Online":        "warning",
        },
    )
    def payment_method_badge(self, obj):
        return obj.get_payment_method_display()

    # ── Computed columns ───────────────────────────────────────────

    @display(description=_("Amount"), ordering="amount")
    def amount_display(self, obj):
        return f"₨ {obj.amount:,.0f}"

    # ── Detail readonly fields ─────────────────────────────────────

    @display(description=_("Document"))
    def document_preview(self, obj):
        if not obj.document:
            return "—"
        return mark_safe(
            f'<a href="{obj.document.url}" target="_blank" '
            f'style="color:#7c3aed;font-weight:500;text-decoration:none;">'
            f'📎 View Document</a>'
        )

    # ── Soft-delete ────────────────────────────────────────────────

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()



@admin.register(Expense.history.model)
class HistoricalExpenseAdmin(UnfoldModelAdmin):
    list_display  = ("category", "amount", "project", "vendor_name", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "category")
    search_fields = ("vendor_name", "description")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Expense.history.model._meta.get_fields()]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False