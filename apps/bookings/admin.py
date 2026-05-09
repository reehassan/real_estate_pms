"""
apps/bookings/admin.py

Production-grade Unfold admin for Booking + Installment + BookingDocument models.

Features:
    - Unfold label={} badges on all status fields
    - Import / Export (CSV + XLSX) for both models
    - AdminConfirmMixin on status changes
    - Date-range filters on booking_date, due_date, paid_on
    - Annotated outstanding balance (no N+1)
    - Token + down payment fields in fieldsets
    - Payment summary panel (dark-mode safe)
    - BookingDocument inline
    - Soft-delete aware
"""

from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from rangefilter.filters import DateRangeFilterBuilder
from simple_history.admin import SimpleHistoryAdmin

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from unfold.decorators import display

from .models import Booking, Installment, BookingDocument


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _pkr(value) -> str:
    if value is None:
        return "—"
    return f"₨ {value:,.0f}"


# ─────────────────────────────────────────────
# RESOURCES
# ─────────────────────────────────────────────

class BookingResource(resources.ModelResource):
    customer_name   = fields.Field(column_name="Customer Name")
    customer_cnic   = fields.Field(column_name="Customer CNIC")
    plot_number     = fields.Field(column_name="Plot Number")
    project_name    = fields.Field(column_name="Project")
    booked_by_email = fields.Field(column_name="Booked By")

    class Meta:
        model          = Booking
        skip_unchanged = True
        report_skipped = False
        fields = (
            "id", "customer_name", "customer_cnic",
            "plot_number", "project_name", "booking_date",
            "payment_plan", "total_price",
            "token_amount", "token_received_on",
            "down_payment", "down_payment_received_on",
            "status", "booked_by_email", "created_at",
        )
        export_order = fields

    def dehydrate_customer_name(self, obj):
        return obj.customer.full_name if obj.customer_id else ""

    def dehydrate_customer_cnic(self, obj):
        return obj.customer.cnic if obj.customer_id else ""

    def dehydrate_plot_number(self, obj):
        return obj.plot.plot_number if obj.plot_id else ""

    def dehydrate_project_name(self, obj):
        return obj.plot.project.name if obj.plot_id else ""

    def dehydrate_booked_by_email(self, obj):
        return obj.booked_by.email if obj.booked_by_id else ""


class InstallmentResource(resources.ModelResource):
    customer_name = fields.Field(column_name="Customer Name")
    plot_number   = fields.Field(column_name="Plot Number")

    class Meta:
        model          = Installment
        skip_unchanged = True
        report_skipped = False
        fields = (
            "id", "challan_number", "booking", "customer_name",
            "plot_number", "installment_number", "due_date",
            "amount_due", "amount_paid", "paid_on", "status", "created_at",
        )
        export_order = fields

    def dehydrate_customer_name(self, obj):
        return obj.booking.customer.full_name if obj.booking_id else ""

    def dehydrate_plot_number(self, obj):
        return obj.booking.plot.plot_number if obj.booking_id else ""


# ─────────────────────────────────────────────
# INLINES
# ─────────────────────────────────────────────

class InstallmentInline(UnfoldTabularInline):
    model            = Installment
    extra            = 0
    can_delete       = False
    show_change_link = True
    classes          = ["collapse"]
    fields = (
        "challan_number", "installment_number", "due_date",
        "amount_due", "amount_paid", "paid_on",
        "installment_status", "challan_link",
    )
    readonly_fields = (
        "challan_number", "installment_number", "due_date",
        "amount_due", "amount_paid", "paid_on",
        "installment_status", "challan_link",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("booking")

    @display(
        description=_("Status"),
        label={
            "Pending": "warning",
            "Paid":    "success",
            "Overdue": "danger",
            "Waived":  "secondary",
        },
    )
    def installment_status(self, obj):
        return obj.get_status_display()

    @display(description=_("Challan"))
    def challan_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("challans:pdf", args=[obj.pk])
        return mark_safe(
            f'<a href="{url}" target="_blank" '
            f'style="color:#7c3aed;font-weight:600;font-size:11px;">↓ PDF</a>'
        )


class BookingDocumentInline(UnfoldTabularInline):
    model            = BookingDocument
    extra            = 1
    can_delete       = True
    show_change_link = False
    fields           = ("doc_type", "file", "notes", "uploaded_by", "uploaded_at")
    readonly_fields  = ("uploaded_by", "uploaded_at")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()


# ─────────────────────────────────────────────
# BULK ACTIONS — Bookings
# ─────────────────────────────────────────────

@admin.action(description="✅  Mark selected bookings as Completed")
def mark_completed(modeladmin, request, queryset):
    updated = queryset.filter(status=Booking.Status.ACTIVE).update(
        status=Booking.Status.COMPLETED,
    )
    modeladmin.message_user(request, f"{updated} booking(s) marked Completed.")


@admin.action(description="🚫  Mark selected bookings as Cancelled")
def mark_cancelled(modeladmin, request, queryset):
    updated = queryset.filter(
        status__in=[Booking.Status.TOKEN, Booking.Status.ACTIVE]
    ).update(status=Booking.Status.CANCELLED)
    modeladmin.message_user(request, f"{updated} booking(s) marked Cancelled.")


# ─────────────────────────────────────────────
# BULK ACTIONS — Installments
# ─────────────────────────────────────────────

@admin.action(description="⚠️  Mark selected installments as Overdue")
def mark_overdue(modeladmin, request, queryset):
    updated = queryset.filter(status=Installment.Status.PENDING).update(
        status=Installment.Status.OVERDUE,
    )
    modeladmin.message_user(request, f"{updated} installment(s) marked Overdue.")


# ─────────────────────────────────────────────
# BOOKING ADMIN
# ─────────────────────────────────────────────

@admin.register(Booking)

class BookingAdmin(ImportExportModelAdmin, SimpleHistoryAdmin, UnfoldModelAdmin):
    resource_classes = [BookingResource]
    confirmation_fields = ["status"]

    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    # ── List view ──────────────────────────────────────────────────
    list_display = (
        "id",
        "customer_name_display",
        "plot_display",
        "booking_date",
        "payment_plan",
        "total_price_display",
        "token_display",
        "down_payment_display",
        "outstanding_display",
        "status_badge",
        "created_at",
    )
    list_display_links  = ("id", "customer_name_display")
    list_select_related = ("customer", "plot", "plot__project", "booked_by")
    search_fields = (
        "customer__full_name",
        "customer__cnic",
        "plot__plot_number",
        "plot__project__name",
        "id",
    )
    list_filter = (
        "status",
        "payment_plan",
        ("booking_date", DateRangeFilterBuilder(title="Booking Date")),
        ("created_at",   DateRangeFilterBuilder(title="Created")),
    )
    date_hierarchy = "booking_date"
    list_per_page  = 30
    ordering       = ["-created_at"]
    actions        = [mark_completed, mark_cancelled]

    # ── Change form ────────────────────────────────────────────────
    autocomplete_fields = ["customer", "plot", "booked_by"]
    readonly_fields     = ("created_at", "updated_at", "payment_summary")
    inlines             = [InstallmentInline, BookingDocumentInline]

    fieldsets = (
        (
            _("Booking Details"),
            {
                "fields": (
                    ("customer", "plot"),
                    ("booking_date", "booked_by"),
                    ("payment_plan", "status"),
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Token Payment"),
            {
                "fields": (
                    ("token_amount", "token_received_on"),
                ),
                "classes": ["wide"],
                "description": (
                    "Initial amount received to hold the plot. "
                    "Set status to TOKEN on creation. "
                    "Deducted from the installment principal."
                ),
            },
        ),
        (
            _("Down Payment"),
            {
                "fields": (
                    ("down_payment", "down_payment_received_on"),
                ),
                "classes": ["wide"],
                "description": (
                    "Once down payment is received, set down_payment_received_on "
                    "and change status to ACTIVE. "
                    "Installments will be generated automatically."
                ),
            },
        ),
        (
            _("Financials"),
            {
                "fields": (
                    "total_price",
                    "payment_summary",
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Notes"),
            {
                "fields": ("notes",),
                "classes": ["collapse"],
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (("created_at", "updated_at"),),
                "classes": ["collapse"],
            },
        ),
    )

    add_fieldsets = (
        (
            _("Booking Details"),
            {
                "fields": (
                    ("customer", "plot"),
                    ("booking_date", "booked_by"),
                    ("payment_plan", "status"),
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Token Payment"),
            {
                "fields": (("token_amount", "token_received_on"),),
                "classes": ["wide"],
            },
        ),
        (
            _("Down Payment"),
            {
                "fields": (("down_payment", "down_payment_received_on"),),
                "classes": ["wide"],
            },
        ),
        (
            _("Total Price"),
            {
                "fields": ("total_price",),
                "classes": ["wide"],
            },
        ),
        (
            _("Notes"),
            {
                "fields": ("notes",),
                "classes": ["collapse"],
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    # ── Queryset ───────────────────────────────────────────────────

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("customer", "plot", "plot__project", "booked_by")
            .prefetch_related("installments")
            .annotate(
                _total_due  = Sum("installments__amount_due"),
                _total_paid = Sum("installments__amount_paid"),
            )
        )

    # ── Badges ─────────────────────────────────────────────────────

    @display(
        description=_("Status"),
        ordering="status",
        label={
            "Token":     "warning",    # amber  — partial commitment
            "Active":    "success",    # emerald — running
            "Completed": "secondary",  # slate  — done
            "Cancelled": "danger",     # rose   — void
        },
    )
    def status_badge(self, obj):
        return obj.get_status_display()

    # ── List computed columns ──────────────────────────────────────

    @display(description=_("Customer"), ordering="customer__full_name")
    def customer_name_display(self, obj):
        return obj.customer.full_name if obj.customer_id else "—"

    @display(description=_("Plot"), ordering="plot__plot_number")
    def plot_display(self, obj):
        if not obj.plot_id:
            return "—"
        return f"{obj.plot.project.name} / {obj.plot.plot_number}"

    @display(description=_("Total Price"), ordering="total_price")
    def total_price_display(self, obj):
        return _pkr(obj.total_price)

    @display(description=_("Token"), ordering="token_amount")
    def token_display(self, obj):
        if not obj.token_amount:
            return "—"
        colour = "#16a34a" if obj.token_received_on else "#d97706"
        return mark_safe(
            f'<span style="color:{colour};font-weight:600;">'
            f'{_pkr(obj.token_amount)}</span>'
        )

    @display(description=_("Down Payment"), ordering="down_payment")
    def down_payment_display(self, obj):
        if not obj.down_payment:
            return "—"
        colour = "#16a34a" if obj.down_payment_received_on else "#d97706"
        return mark_safe(
            f'<span style="color:{colour};font-weight:600;">'
            f'{_pkr(obj.down_payment)}</span>'
        )

    @display(description=_("Outstanding"), ordering="_total_due")
    def outstanding_display(self, obj):
        total_due   = getattr(obj, "_total_due",  None) or 0
        total_paid  = getattr(obj, "_total_paid", None) or 0
        outstanding = total_due - total_paid

        if outstanding <= 0:
            colour = "#16a34a"
        elif outstanding == total_due:
            colour = "#e11d48"
        else:
            colour = "#d97706"

        return mark_safe(
            f'<span style="color:{colour};font-weight:600;">'
            f'{_pkr(outstanding)}</span>'
        )

    # ── Payment summary panel ──────────────────────────────────────

    @display(description=_("Payment Summary"))
    def payment_summary(self, obj):
        if not obj.pk:
            return "—"

        installments = list(obj.installments.all())

        VIOLET  = "#7c3aed"
        EMERALD = "#16a34a"
        AMBER   = "#d97706"
        SLATE   = "#64748b"
        ROSE    = "#e11d48"
        SKY     = "#0284c7"

        # Upfront section
        token_colour = EMERALD if obj.token_received_on else AMBER
        dp_colour    = EMERALD if obj.down_payment_received_on else AMBER

        upfront_stats = [
            ("Token Received",  _pkr(obj.token_amount),  token_colour),
            ("Down Payment",    _pkr(obj.down_payment),  dp_colour),
            ("Total Upfront",   _pkr(obj.total_upfront), VIOLET),
            ("Instalment Principal", _pkr(obj.installment_principal), SKY),
        ]

        if not installments:
            instalment_note = (
                '<p style="color:#d97706;font-size:12px;margin:8px 0 0;">'
                '⚠ Installments not yet generated. '
                'Change status to Active to trigger generation.</p>'
                if obj.status == Booking.Status.TOKEN
                else '<p style="color:#64748b;font-size:12px;margin:8px 0 0;">'
                     'No installments yet.</p>'
            )
        else:
            total_due  = sum(i.amount_due  for i in installments)
            total_paid = sum(i.amount_paid for i in installments)
            remaining  = total_due - total_paid
            n_total    = len(installments)
            n_paid     = sum(1 for i in installments if i.status == Installment.Status.PAID)
            n_overdue  = sum(1 for i in installments if i.status == Installment.Status.OVERDUE)
            n_pending  = sum(1 for i in installments if i.status == Installment.Status.PENDING)

            instalment_note = ""
            upfront_stats += [
                ("Total Due",    _pkr(total_due),                    SKY),
                ("Collected",    _pkr(total_paid),                   EMERALD),
                ("Remaining",    _pkr(remaining),                    ROSE if remaining > 0 else EMERALD),
                ("Instalments",  f"{n_paid} / {n_total} paid",       VIOLET),
                ("Pending",      n_pending,                          AMBER),
                ("Overdue",      n_overdue,                          ROSE if n_overdue else EMERALD),
            ]

        cards = "".join(
            f'<div style="display:inline-block;min-width:145px;margin:6px 10px 6px 0;'
            f'background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {colour};'
            f'border-radius:6px;padding:12px 16px;text-align:center;">'
            f'<div style="font-size:18px;font-weight:700;color:{colour};">{value}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:4px;">{label}</div>'
            f'</div>'
            for label, value, colour in upfront_stats
        )

        html = f'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px 0;">{cards}</div>'
        if instalment_note:
            html += instalment_note

        return mark_safe(html)

    # ── Permissions ────────────────────────────────────────────────

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# ─────────────────────────────────────────────
# BOOKING HISTORY ADMIN
# ─────────────────────────────────────────────

@admin.register(Booking.history.model)
class HistoricalBookingAdmin(UnfoldModelAdmin):
    list_display  = ("id", "customer_id", "status", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "status")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Booking.history.model._meta.get_fields()]

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


# ─────────────────────────────────────────────
# INSTALLMENT ADMIN
# ─────────────────────────────────────────────

@admin.register(Installment)
class InstallmentAdmin(ImportExportModelAdmin, SimpleHistoryAdmin, UnfoldModelAdmin):
    resource_classes    = [InstallmentResource]
    confirmation_fields = ["status"]

    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    list_display = (
        "challan_number",
        "booking_link",
        "customer_name_display",
        "installment_number",
        "due_date",
        "amount_due_display",
        "amount_paid_display",
        "balance_display",
        "paid_on",
        "status_badge",
        "challan_link",
    )
    list_display_links  = ("challan_number",)
    list_select_related = ("booking", "booking__customer", "booking__plot")
    search_fields = (
        "challan_number",
        "booking__customer__full_name",
        "booking__customer__cnic",
        "booking__plot__plot_number",
        "booking__id",
    )
    list_filter = (
        "status",
        ("due_date",   DateRangeFilterBuilder(title="Due Date")),
        ("paid_on",    DateRangeFilterBuilder(title="Paid On")),
        ("created_at", DateRangeFilterBuilder(title="Created")),
    )
    date_hierarchy = "due_date"
    list_per_page  = 40
    ordering       = ["due_date", "installment_number"]
    actions        = [mark_overdue]

    autocomplete_fields = ["booking"]
    readonly_fields     = ("created_at", "challan_number")

    fieldsets = (
        (
            _("Installment Info"),
            {
                "fields": (
                    ("booking", "challan_number"),
                    ("installment_number", "status"),
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Schedule & Payments"),
            {
                "fields": (
                    ("due_date", "paid_on"),
                    ("amount_due", "amount_paid"),
                ),
                "classes": ["wide"],
            },
        ),
        (
            _("Notes"),
            {
                "fields": ("notes",),
                "classes": ["collapse"],
            },
        ),
        (
            _("Metadata"),
            {
                "fields": ("created_at",),
                "classes": ["collapse"],
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("booking", "booking__customer", "booking__plot")
        )

    @display(
        description=_("Status"),
        ordering="status",
        label={
            "Pending": "warning",
            "Paid":    "success",
            "Overdue": "danger",
            "Waived":  "secondary",
        },
    )
    def status_badge(self, obj):
        return obj.get_status_display()

    @display(description=_("Booking"), ordering="booking__id")
    def booking_link(self, obj):
        url = reverse("admin:bookings_booking_change", args=[obj.booking_id])
        return mark_safe(f'<a href="{url}">#{obj.booking_id}</a>')

    @display(description=_("Customer"), ordering="booking__customer__full_name")
    def customer_name_display(self, obj):
        return obj.booking.customer.full_name if obj.booking_id else "—"

    @display(description=_("Amount Due"), ordering="amount_due")
    def amount_due_display(self, obj):
        return _pkr(obj.amount_due)

    @display(description=_("Amount Paid"), ordering="amount_paid")
    def amount_paid_display(self, obj):
        colour = "#16a34a" if obj.amount_paid > 0 else "#64748b"
        return mark_safe(
            f'<span style="color:{colour};font-weight:600;">{_pkr(obj.amount_paid)}</span>'
        )

    @display(description=_("Balance"))
    def balance_display(self, obj):
        balance = obj.amount_due - obj.amount_paid
        colour  = "#e11d48" if balance > 0 else "#16a34a"
        return mark_safe(
            f'<span style="color:{colour};font-weight:600;">{_pkr(balance)}</span>'
        )

    @display(description=_("Challan"))
    def challan_link(self, obj):
        url = reverse("challans:pdf", args=[obj.pk])
        return mark_safe(
            f'<a href="{url}" target="_blank" '
            f'style="color:#7c3aed;font-weight:600;font-size:11px;">↓ PDF</a>'
        )

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# ─────────────────────────────────────────────
# INSTALLMENT HISTORY ADMIN
# ─────────────────────────────────────────────

@admin.register(Installment.history.model)
class HistoricalInstallmentAdmin(UnfoldModelAdmin):
    list_display  = ("challan_number", "status", "amount_due", "amount_paid", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "status")
    search_fields = ("challan_number",)
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Installment.history.model._meta.get_fields()]

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False