from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):

    list_display = [
        'id',
        'project',
        'category',
        'amount',
        'vendor_name',
        'date',
        'payment_method',
        'status',
        'submitted_by',
        'approved_by',
        'is_deleted',
    ]

    list_filter = [
        'status',
        'category',
        'payment_method',
        'project',
        'is_deleted',
    ]

    search_fields = [
        'vendor_name',
        'description',
        'reference_number',
        'project__name',
        'submitted_by__username',
    ]

    readonly_fields = ['created_at', 'updated_at', 'submitted_by', 'approved_by']

    fieldsets = (
        ('Expense Details', {
            'fields': (
                'project',
                'category',
                'amount',
                'vendor_name',
                'description',
                'date',
            )
        }),
        ('Payment Info', {
            'fields': (
                'payment_method',
                'reference_number',
            )
        }),
        ('Status & Approval', {
            'fields': (
                'status',
                'submitted_by',
                'approved_by',
            )
        }),
        ('System', {
            'fields': ('is_deleted', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        # Show all in admin including soft-deleted, for data correction
        return super().get_queryset(request)