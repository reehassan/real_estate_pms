from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display    = ('full_name', 'cnic', 'phone', 'customer_type', 'is_deleted', 'created_at')
    list_filter     = ('customer_type', 'is_deleted')
    search_fields   = ('full_name', 'cnic', 'phone')
    ordering        = ('full_name',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')

    def get_queryset(self, request):
        return Customer.all_objects.all()