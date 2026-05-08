"""
apps/projects_and_plots/admin.py

Production-grade Unfold admin for Project and Plot models.

Features:
    - Card-style Project changelist with logo / banner
    - Import / Export (CSV + XLSX) for both models
    - PlotInline inside Project detail page (editable status)
    - Date-range filters on created_at / updated_at
    - Soft-delete aware
    - Financial summary panel with token count
    - Bulk status change actions
    - Correct Slate + Violet colour mapping on all badges
"""

from django.contrib import admin
from django.db.models import Sum, Count, Q
from django.utils.translation import gettext_lazy as _
from django.utils.html import mark_safe

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from rangefilter.filters import DateRangeFilterBuilder
from simple_history.admin import SimpleHistoryAdmin

from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from django.urls import reverse



from .models import Project, Plot


# ─────────────────────────────────────────────
# RESOURCES
# ─────────────────────────────────────────────

class ProjectResource(resources.ModelResource):
    class Meta:
        model            = Project
        skip_unchanged   = True
        report_skipped   = False
        import_id_fields = ("code",)
        fields = (
            "id", "name", "code", "location",
            "total_plots", "total_area", "area_unit",
            "status", "description", "created_at",
        )
        export_order = fields


class PlotResource(resources.ModelResource):
    project_name = fields.Field(
        column_name="Project",
        attribute="project",
        widget=ForeignKeyWidget(Project, "name"),
    )
    project_code = fields.Field(
        column_name="Project Code",
        attribute="project",
        widget=ForeignKeyWidget(Project, "code"),
    )

    class Meta:
        model            = Plot
        skip_unchanged   = True
        report_skipped   = False
        import_id_fields = ("project", "plot_number")
        fields = (
            "id", "project_name", "project_code",
            "plot_number", "block", "size", "size_unit",
            "category", "price", "status", "notes", "created_at",
        )
        export_order = fields


# ─────────────────────────────────────────────
# INLINE
# ─────────────────────────────────────────────

class PlotInline(TabularInline):
    model            = Plot
    extra            = 0
    can_delete       = False
    show_change_link = True
    fields = (
        "plot_number", "block", "size",
        "size_unit", "category", "price", "status",
    )
    # status is intentionally editable here — removed from readonly_fields

    def get_queryset(self, request):
        # Only show non-deleted plots in the inline
        return super().get_queryset(request).filter(is_deleted=False)


# ─────────────────────────────────────────────
# BULK ACTIONS — Projects
# ─────────────────────────────────────────────

@admin.action(description="▶️  Mark selected projects as Active")
def mark_active(modeladmin, request, queryset):
    updated = queryset.update(status=Project.Status.ACTIVE)
    modeladmin.message_user(request, f"{updated} project(s) marked Active.")


@admin.action(description="⏸️  Mark selected projects as On Hold")
def mark_on_hold(modeladmin, request, queryset):
    updated = queryset.update(status=Project.Status.ON_HOLD)
    modeladmin.message_user(request, f"{updated} project(s) put On Hold.")


@admin.action(description="✅  Mark selected projects as Completed")
def mark_completed(modeladmin, request, queryset):
    updated = queryset.update(status=Project.Status.COMPLETED)
    modeladmin.message_user(request, f"{updated} project(s) marked Completed.")


# ─────────────────────────────────────────────
# BULK ACTIONS — Plots
# ─────────────────────────────────────────────

@admin.action(description="🏷️  Mark selected plots as Available")
def mark_available(modeladmin, request, queryset):
    updated = queryset.update(status=Plot.Status.AVAILABLE)
    modeladmin.message_user(request, f"{updated} plot(s) marked Available.")


@admin.action(description="🔒  Mark selected plots as Booked")
def mark_booked(modeladmin, request, queryset):
    updated = queryset.update(status=Plot.Status.BOOKED)
    modeladmin.message_user(request, f"{updated} plot(s) marked Booked.")


# ─────────────────────────────────────────────
# PROJECT RESULT WRAPPER
# ─────────────────────────────────────────────

class ProjectResult:
    """
    Thin wrapper passed to the card template.
    Carries the object, its edit URL, and pre-fetched plot stats.
    """
    def __init__(self, obj, change_url):
        self.object     = obj
        self.change_url = change_url

        agg = Plot.objects.filter(project=obj).aggregate(
            total     = Count("id"),
            available = Count("id", filter=Q(status=Plot.Status.AVAILABLE)),
            token     = Count("id", filter=Q(status=Plot.Status.TOKEN)),
            booked    = Count("id", filter=Q(status=Plot.Status.BOOKED)),
            sold      = Count("id", filter=Q(status=Plot.Status.SOLD)),
        )
        self.object.plot_stats = type("Stats", (), agg)()


# ─────────────────────────────────────────────
# PROJECT ADMIN
# ─────────────────────────────────────────────

@admin.register(Project)
class ProjectAdmin(ImportExportModelAdmin, SimpleHistoryAdmin, ModelAdmin):
    resource_classes   = [ProjectResource]
    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    # Uncomment when card template is in place:
    # change_list_template = "admin/projects_and_plots/project/change_list.html"

    list_display = (
        "name", "code", "location",
        "status_badge", "total_plots",
        "total_area", "area_unit", "created_at",
    )
    list_display_links = ("name", "code")
    search_fields      = ("name", "code", "location", "description")
    ordering           = ("-created_at",)
    date_hierarchy     = "created_at"
    list_per_page      = 25
    actions            = [mark_active, mark_on_hold, mark_completed]
    list_filter = (
        "status",
        "area_unit",
        ("created_at", DateRangeFilterBuilder(title="Created")),
        ("updated_at", DateRangeFilterBuilder(title="Last Updated")),
    )

    readonly_fields = ("created_at", "updated_at", "project_financial_summary", "project_report_links")
    inlines         = [PlotInline]

    fieldsets = (
        (
            _("Project Details"),
            {
                "fields": ("name", "code", "location", "description", "status"),
                "classes": ["wide"],
            },
        ),
        (
            _("Logo / Banner"),
            {
                "fields": ("logo",),
                "classes": ["wide"],
                "description": "Recommended size: 800 × 200 px. Shown on the projects card view.",
            },
        ),
        (
            _("Area & Scale"),
            {
                "fields": ("total_plots", "total_area", "area_unit"),
                "classes": ["wide"],
            },
        ),
        (
            _("Financial Summary"),
            {
                "fields": ("project_financial_summary",),
                "classes": ["wide"],
                "description": "Aggregated stats from all plots in this project.",
            },
        ),
        (
            _("Reports"),
            {
                "fields": ("project_report_links",),
                "classes": ["wide"],
                "description": "Download Excel reports scoped to this project.",
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created_at", "updated_at"),
                "classes": ["wide"],
            },
        ),
    )

    # ── Card view context injection ────────────────────────────────
    # Only active when change_list_template is uncommented above

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            cl = response.context_data["cl"]
        except (AttributeError, KeyError):
            return response

        results = []
        for obj in cl.queryset:
            change_url = self.get_change_url(request, obj)
            results.append(ProjectResult(obj, change_url))

        response.context_data["results"]             = results
        response.context_data["has_add_permission"]  = self.has_add_permission(request)
        return response

    def get_change_url(self, request, obj):
        from django.urls import reverse
        info = self.model._meta.app_label, self.model._meta.model_name
        return reverse("admin:%s_%s_change" % info, args=[obj.pk])

    # ── Badges ─────────────────────────────────────────────────────

    @display(
        description=_("Status"),
        ordering="status",
        label={
            "Planning":  "info",       # sky  — future/neutral
            "Active":    "success",    # emerald — healthy/running
            "On Hold":   "warning",    # amber — caution/paused
            "Completed": "secondary",  # slate — done/archived
        },
    )
    def status_badge(self, obj: Project) -> str:
        return obj.get_status_display()

    # ── Financial summary panel ────────────────────────────────────

    @display(description=_("Financial Summary"))
    def project_financial_summary(self, obj: Project) -> str:
        agg = Plot.objects.filter(project=obj).aggregate(
            total_plots     = Count("id"),
            available_count = Count("id", filter=Q(status=Plot.Status.AVAILABLE)),
            token_count     = Count("id", filter=Q(status=Plot.Status.TOKEN)),
            booked_count    = Count("id", filter=Q(status=Plot.Status.BOOKED)),
            sold_count      = Count("id", filter=Q(status=Plot.Status.SOLD)),
            total_value     = Sum("price"),
            sold_value      = Sum("price", filter=Q(status=Plot.Status.SOLD)),
            booked_value    = Sum("price", filter=Q(status=Plot.Status.BOOKED)),
        )

        def fmt(val):
            return f"₨ {val:,.0f}" if val else "₨ 0"

        # Slate + Violet palette — hex values matching your theme tokens
        VIOLET  = "#7c3aed"   # primary
        EMERALD = "#16a34a"   # success
        AMBER   = "#d97706"   # warning
        SLATE   = "#64748b"   # secondary
        SKY     = "#0284c7"   # info
        ROSE    = "#e11d48"   # danger

        stats = [
            ("Total Plots",   agg["total_plots"],     SLATE),
            ("Available",     agg["available_count"], EMERALD),
            ("Token",         agg["token_count"],     AMBER),
            ("Booked",        agg["booked_count"],    VIOLET),
            ("Sold",          agg["sold_count"],      SLATE),
            ("Total Value",   fmt(agg["total_value"]),  SKY),
            ("Sold Revenue",  fmt(agg["sold_value"]),   EMERALD),
            ("Booked Value",  fmt(agg["booked_value"]), VIOLET),
        ]

        cards = "".join(
            f'<div style="display:inline-block;min-width:150px;margin:6px 10px 6px 0;'
            f'background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {colour};'
            f'border-radius:6px;padding:14px 18px;text-align:center;">'
            f'<div style="font-size:22px;font-weight:700;color:{colour};">{value}</div>'
            f'<div style="font-size:12px;color:#64748b;margin-top:4px;">{label}</div>'
            f'</div>'
            for label, value, colour in stats
        )
        return mark_safe(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px 0;">{cards}</div>'
        )
    @display(description=_("Reports"))
    def project_report_links(self, obj: Project) -> str:
        """
        Rendered as a readonly field on the project change form.
        Each button links to the matching Excel report view.
        """
        if not obj.pk:
            return "Save the project first to generate reports."
 
        BTN = (
            "display:inline-block;margin:4px 8px 4px 0;"
            "padding:8px 16px;border-radius:6px;"
            "font-size:12px;font-weight:600;text-decoration:none;"
            "color:#fff;background:{bg};"
        )
        reports = [
            (" Plot Inventory",    "reports:project_plot_inventory",   "#0284c7"),
            (" Revenue",           "reports:project_revenue",          "#16a34a"),
            (" Expenses",          "reports:project_expenses",         "#7c3aed"),
            (" Per-Plot Detail",   "reports:project_per_plot_detail",  "#1e293b"),
        ]
        links = "".join(
            f'<a href="{reverse(name, args=[obj.pk])}" target="_blank" '
            f'style="{BTN.format(bg=colour)}">{label}</a>'
            for label, name, colour in reports
        )
        return mark_safe(
            f'<div style="padding:8px 0;">{links}</div>'
            f'<p style="font-size:11px;color:#64748b;margin-top:8px;">'
            f'Each link downloads an Excel file immediately.</p>'
        )

    # ── Soft-delete ────────────────────────────────────────────────

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()

@admin.register(Project.history.model)
class HistoricalProjectAdmin(UnfoldModelAdmin):
    list_display  = ("name", "code", "status", "location", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "status")
    search_fields = ("name", "code", "location")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Project.history.model._meta.get_fields()]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False



# ─────────────────────────────────────────────
# PLOT ADMIN
# ─────────────────────────────────────────────

@admin.register(Plot)
class PlotAdmin(ImportExportModelAdmin, SimpleHistoryAdmin, ModelAdmin):
    resource_classes   = [PlotResource]
    compressed_fields  = True
    warn_unsaved_form  = True
    list_filter_submit = True

    list_display = (
        "plot_number", "project", "block",
        "size_display", "category_badge",
        "status_badge", "price_display", "created_at",
    )
    list_display_links  = ("plot_number",)
    list_select_related = ("project",)
    search_fields = (
        "plot_number", "block",
        "project__name", "project__code",
    )
    ordering       = ("project", "block", "plot_number")
    date_hierarchy = "created_at"
    list_per_page  = 30
    actions        = [mark_available, mark_booked]
    list_filter = (
        "status",
        "category",
        "size_unit",
        "project",
        ("created_at", DateRangeFilterBuilder(title="Created")),
        ("updated_at", DateRangeFilterBuilder(title="Last Updated")),
    )

    readonly_fields     = ("created_at", "updated_at")
    autocomplete_fields = ("project",)

    fieldsets = (
        (
            _("Identification"),
            {
                "fields": ("project", "plot_number", "block"),
                "classes": ["wide"],
                "description": (
                    "Plot numbers must match the approved layout plan. "
                    "Do not guess or auto-generate — they appear on legal documents."
                ),
            },
        ),
        (
            _("Physical Details"),
            {"fields": ("size", "size_unit", "category"), "classes": ["wide"]},
        ),
        (
            _("Financials & Status"),
            {"fields": ("price", "status", "notes"), "classes": ["wide"]},
        ),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ["wide"]},
        ),
    )

    # ── Badges ─────────────────────────────────────────────────────

    @display(
        description=_("Status"),
        ordering="status",
        label={
            "Available": "success",    # emerald — open/good
            "Token":     "warning",    # amber   — partial commitment
            "Booked":    "primary",    # violet  — committed/in progress
            "Sold":      "secondary",  # slate   — closed/done
        },
    )
    def status_badge(self, obj: Plot) -> str:
        return obj.get_status_display()

    @display(
        description=_("Category"),
        ordering="category",
        label={
            "Residential": "info",     # sky    — common/neutral
            "Commercial":  "warning",  # amber  — notable/distinct
        },
    )
    def category_badge(self, obj: Plot) -> str:
        return obj.get_category_display()

    @display(description=_("Size"), ordering="size")
    def size_display(self, obj: Plot) -> str:
        return f"{obj.size} {obj.get_size_unit_display()}"

    @display(description=_("Price"), ordering="price")
    def price_display(self, obj: Plot) -> str:
        return f"₨ {obj.price:,.0f}"

    # ── Soft-delete ────────────────────────────────────────────────

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()



@admin.register(Plot.history.model)
class HistoricalPlotAdmin(UnfoldModelAdmin):
    list_display  = ("plot_number", "project", "status", "price", "category", "history_date", "history_type", "history_user")
    list_filter   = ("history_type", "status", "category")
    search_fields = ("plot_number", "block", "project__name")
    ordering      = ("-history_date",)
    list_per_page = 40
    readonly_fields = [f.name for f in Plot.history.model._meta.get_fields()]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False