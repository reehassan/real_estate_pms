"""
apps/customers/admin.py

Production-ready Unfold admin for Customer model.

Features:
    - Unfold label={} badges for all status/type fields
    - Booking history inline (lazy import, correct queryset)
    - Financial overview panel
    - Date-range filter on created_at
    - Annotated booking_count for performance
    - Dark-mode safe throughout
"""

from django.contrib import admin
from django.db.models import Count, Sum
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from unfold.decorators import display
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin


from rangefilter.filters import DateRangeFilterBuilder

from .models import Customer


# ─────────────────────────────────────────────
# BOOKING INLINE
# ─────────────────────────────────────────────

class BookingInline(UnfoldTabularInline):
    extra            = 0
    can_delete       = False
    show_change_link = True
    fields = (
        "plot", "booking_date", "payment_plan",
        "total_price", "down_payment", "booking_status",
    )
    readonly_fields = (
        "plot", "booking_date", "payment_plan",
        "total_price", "down_payment", "booking_status",
    )

    def get_queryset(self, request):
        from apps.bookings.models import Booking
        # Django inline machinery handles filtering by customer FK automatically.
        # We just add select_related for query efficiency.
        return Booking.objects.select_related("plot__project")

    @display(
        description=_("Status"),
        label={
            "Draft":     "secondary",
            "Confirmed": "primary",
            "Active":    "success",
            "Cancelled": "danger",
            "Expired":   "warning",
        },
    )
    def booking_status(self, obj):
        return obj.get_status_display()


# ─────────────────────────────────────────────
# CUSTOMER ADMIN
# ─────────────────────────────────────────────

@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin,UnfoldModelAdmin):

    # ── Unfold UI ──────────────────────────────────────────────────
    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    # ── List page ──────────────────────────────────────────────────
    list_display = (
        "full_name",
        "cnic",
        "phone",
        "type_badge",
        "booking_count",
        "created_at",
    )
    list_filter = (
        "customer_type",
        ("created_at", DateRangeFilterBuilder(title="Date Added")),
    )
    search_fields = ("full_name", "cnic", "phone", "address")
    ordering      = ("full_name",)
    list_per_page = 25
    list_select_related = True

    # ── Detail page ────────────────────────────────────────────────
    readonly_fields = ("created_at", "updated_at", "financial_overview")

    fieldsets = (
        (
            _("Personal Details"),
            {
                "fields": (
                    "full_name",
                    ("cnic", "phone"),
                    "customer_type",
                    "address",
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Financial Overview"),
            {
                "fields": ("financial_overview",),
                "classes": ["wide"],
                "description": "Live stats pulled from all bookings linked to this customer.",
            },
        ),
        (
            _("Record Info"),
            {
                "fields": ("created_at", "updated_at"),
                "classes": ["collapse"],
            },
        ),
    )

    def get_inlines(self, request, obj=None):
        """Show booking inline only on existing customers, not on the add form."""
        if not obj:
            return []
        # Set model here to avoid circular import at module level
        from apps.bookings.models import Booking
        BookingInline.model = Booking
        return [BookingInline]

    # ── Queryset ───────────────────────────────────────────────────

    def get_queryset(self, request):
        return (
            Customer.objects
            .annotate(booking_count=Count("bookings", distinct=True))
        )

    # ── List display methods ───────────────────────────────────────

    @display(
        description=_("Type"),
        ordering="customer_type",
        label={
            "Individual": "info",      # sky    — common/neutral
            "Joint":      "primary",   # violet — shared/notable
            "Corporate":  "success",   # emerald — business/formal
        },
    )
    def type_badge(self, obj):
        return obj.get_customer_type_display()

    @display(description=_("Bookings"), ordering="booking_count")
    def booking_count(self, obj):
        count = getattr(obj, "booking_count", 0)
        return count if count else "—"

    # ── Financial overview panel ───────────────────────────────────

    @display(description=_("Financial Overview"))
    def financial_overview(self, obj):
        if not obj.pk:
            return "—"

        from apps.bookings.models import Booking, Installment

        bookings       = Booking.objects.filter(customer=obj)
        total_bookings = bookings.count()

        if not total_bookings:
            return "No bookings yet."

        totals = bookings.aggregate(
            total_value    = Sum("total_price"),
            total_down     = Sum("down_payment"),
        )

        installments = Installment.objects.filter(booking__customer=obj)
        paid_amount  = installments.filter(status="paid").aggregate(
            t=Sum("amount_paid")
        )["t"] or 0
        overdue_count = installments.filter(status="overdue").count()
        pending_count = installments.filter(status="pending").count()

        total_value = totals["total_value"] or 0
        remaining   = total_value - paid_amount

        # ── Stat cards ─────────────────────────────────────────────
        VIOLET  = "#7c3aed"
        EMERALD = "#16a34a"
        AMBER   = "#d97706"
        SLATE   = "#64748b"
        ROSE    = "#e11d48"
        SKY     = "#0284c7"

        stats = [
            ("Bookings",     total_bookings,              VIOLET),
            ("Total Value",  f"₨ {total_value:,.0f}",    SKY),
            ("Collected",    f"₨ {paid_amount:,.0f}",    EMERALD),
            ("Remaining",    f"₨ {remaining:,.0f}",      SLATE),
            ("Pending",      pending_count,               AMBER),
            ("Overdue",      overdue_count,               ROSE if overdue_count else EMERALD),
        ]

        cards = "".join(
            f'<div style="display:inline-block;min-width:140px;margin:6px 10px 6px 0;'
            f'background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {colour};'
            f'border-radius:6px;padding:12px 16px;text-align:center;">'
            f'<div style="font-size:20px;font-weight:700;color:{colour};">{value}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:4px;">{label}</div>'
            f'</div>'
            for label, value, colour in stats
        )
        return mark_safe(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px 0;">{cards}</div>'
        )

    # ── Soft-delete awareness ──────────────────────────────────────

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


@admin.register(Customer.history.model)
class HistoricalCustomerAdmin(UnfoldModelAdmin):
    list_display  = ("full_name", "cnic", "phone", "customer_type", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "customer_type")
    search_fields = ("full_name", "cnic", "phone")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Customer.history.model._meta.get_fields()]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False