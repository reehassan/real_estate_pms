from django.contrib import admin
from .models import Booking, Installment


class InstallmentInline(admin.TabularInline):
    model           = Installment
    extra           = 0
    readonly_fields = ('challan_number', 'installment_number', 'due_date',
                       'amount_due', 'amount_paid', 'paid_on', 'status', 'created_at')
    can_delete      = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display    = ('id', 'customer', 'plot', 'payment_plan', 'status',
                       'total_price', 'down_payment', 'booked_by', 'is_deleted', 'created_at')
    list_filter     = ('status', 'payment_plan', 'is_deleted')
    search_fields   = ('customer__full_name', 'customer__cnic', 'plot__plot_number')
    ordering        = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    inlines         = [InstallmentInline]

    def get_queryset(self, request):
        return Booking.all_objects.all()


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):

    list_display    = ('challan_number', 'booking', 'installment_number',
                       'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter     = ('status',)
    search_fields   = ('challan_number', 'booking__customer__full_name')
    ordering        = ('due_date', 'installment_number')
    readonly_fields = ('challan_number', 'installment_number', 'due_date',
                       'amount_due', 'created_at')