from django.contrib import admin
from .models import Project, Plot


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    list_display    = ('name', 'location', 'status', 'total_area', 'area_unit', 'is_deleted', 'created_at')
    list_filter     = ('status', 'area_unit', 'is_deleted')
    search_fields   = ('name', 'location')
    ordering        = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')

    def get_queryset(self, request):
        return Project.all_objects.all()


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):

    list_display    = ('plot_number', 'project', 'block', 'size', 'size_unit', 'category', 'price', 'status', 'is_deleted')
    list_filter     = ('status', 'category', 'size_unit', 'is_deleted')
    search_fields   = ('plot_number', 'block', 'project__name')
    ordering        = ('project', 'block', 'plot_number')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')

    def get_queryset(self, request):
        return Plot.all_objects.all()