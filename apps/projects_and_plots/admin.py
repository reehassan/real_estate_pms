# apps/projects/admin.py

from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.html import format_html

from .models import Project, Plot


# ──────────────────────────────────────────────────────────────────────────────
# INLINES
# ──────────────────────────────────────────────────────────────────────────────

class PlotInlineAdmin(admin.TabularInline):
    model = Plot
    extra = 1
    fields = ('plot_number', 'block', 'size', 'size_unit', 'category', 'price', 'status', 'notes')
    show_change_link = True

    def get_queryset(self, request):
        """Only show non‑deleted plots inside the project form."""
        return super().get_queryset(request).filter(is_deleted=False)


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOM LIST FILTER TO SHOW DELETED RECORDS
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
            return queryset.model.all_objects.all()  # show everything
        # Default: exclude deleted records
        return queryset.filter(is_deleted=False)


# ──────────────────────────────────────────────────────────────────────────────
# PROJECT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'total_plots', 'status', 'active_plots_count', 'created_at')
    list_display_links = ('name',)
    list_filter = ('status', 'area_unit', DeletedFilter, 'created_at')  # replaces is_deleted filter
    search_fields = ('name', 'location', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'active_plots_link')
    ordering = ('-created_at',)
    fieldsets = (
        (_('Basic Information'), {'fields': ('name', 'location', 'description', 'status')}),
        (_('Area & Size'), {'fields': ('total_plots', 'total_area', 'area_unit'), 'classes': ('wide',)}),
        (_('Soft Delete'), {'fields': ('deleted_at',), 'classes': ('collapse',)}),  # is_deleted not editable directly
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    inlines = [PlotInlineAdmin]
    actions = ['restore_selected', 'mark_active', 'mark_completed']

    def get_queryset(self, request):
        """Default: exclude soft‑deleted projects."""
        return Project.objects.all()  # uses SoftDeleteManager

    @admin.display(description=_('Active Plots'))
    def active_plots_count(self, obj):
        return obj.plots.filter(is_deleted=False).count()

    @admin.display(description=_('Plots (view)'))
    def active_plots_link(self, obj):
        url = reverse('admin:projects_and_plots_plot_changelist') + f'?project__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, _('View Plots'))

    @admin.action(description=_('Restore selected projects'))
    def restore_selected(self, request, queryset):
        updated = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_at=None)
        self.message_user(request, _('%(count)d project(s) were restored.') % {'count': updated}, messages.SUCCESS)

    @admin.action(description=_('Mark as Active'))
    def mark_active(self, request, queryset):
        updated = queryset.update(status=Project.Status.ACTIVE)
        self.message_user(request, _('%(count)d project(s) marked as Active.') % {'count': updated})

    @admin.action(description=_('Mark as Completed'))
    def mark_completed(self, request, queryset):
        updated = queryset.update(status=Project.Status.COMPLETED)
        self.message_user(request, _('%(count)d project(s) marked as Completed.') % {'count': updated})

    def delete_model(self, request, obj):
        obj.delete()  # soft delete
        self.message_user(request, _('Project “%(name)s” was soft‑deleted.') % {'name': obj.name}, messages.WARNING)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()
        self.message_user(request, _('Selected projects were soft‑deleted.'), messages.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# PLOT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = ('plot_number', 'project_link', 'block', 'size_display', 'category', 'price', 'status', 'created_at')
    list_display_links = ('plot_number',)
    list_filter = ('status', 'category', 'size_unit', 'project', DeletedFilter, 'created_at')
    search_fields = ('plot_number', 'block', 'project__name', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    raw_id_fields = ('project',)
    autocomplete_fields = ('project',)
    list_select_related = ('project',)
    list_per_page = 50
    fieldsets = (
        (_('Project & Identification'), {'fields': ('project', 'plot_number', 'block')}),
        (_('Physical Details'), {'fields': ('size', 'size_unit', 'category')}),
        (_('Financial'), {'fields': ('price',)}),
        (_('Status & Notes'), {'fields': ('status', 'notes')}),
        (_('Soft Delete'), {'fields': ('deleted_at',), 'classes': ('collapse',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    actions = ['restore_selected', 'mark_available', 'mark_booked', 'mark_sold']

    def get_queryset(self, request):
        """Default: exclude soft‑deleted plots."""
        return Plot.objects.select_related('project').all()

    @admin.display(description=_('Project'), ordering='project__name')
    def project_link(self, obj):
        url = reverse('admin:projects_and_plots_project_change', args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.name)

    @admin.display(description=_('Size'))
    def size_display(self, obj):
        return f"{obj.size} {obj.get_size_unit_display()}"

    @admin.action(description=_('Restore selected plots'))
    def restore_selected(self, request, queryset):
        updated = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_at=None)
        self.message_user(request, _('%(count)d plot(s) were restored.') % {'count': updated}, messages.SUCCESS)

    @admin.action(description=_('Mark as Available'))
    def mark_available(self, request, queryset):
        updated = queryset.update(status=Plot.Status.AVAILABLE)
        self.message_user(request, _('%(count)d plot(s) marked as Available.') % {'count': updated})

    @admin.action(description=_('Mark as Booked'))
    def mark_booked(self, request, queryset):
        updated = queryset.update(status=Plot.Status.BOOKED)
        self.message_user(request, _('%(count)d plot(s) marked as Booked.') % {'count': updated})

    @admin.action(description=_('Mark as Sold'))
    def mark_sold(self, request, queryset):
        updated = queryset.update(status=Plot.Status.SOLD)
        self.message_user(request, _('%(count)d plot(s) marked as Sold.') % {'count': updated})

    def delete_model(self, request, obj):
        obj.delete()
        self.message_user(request, _('Plot “%(plot)s” was soft‑deleted.') % {'plot': str(obj)}, messages.WARNING)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()
        self.message_user(request, _('Selected plots were soft‑deleted.'), messages.WARNING)