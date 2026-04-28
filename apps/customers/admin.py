from django.contrib import admin
from .models import Customer
from apps.bookings.models import Booking, Installment


class InstallmentInline(admin.TabularInline):
    model           = Installment
    extra           = 0
    readonly_fields = ('challan_number', 'installment_number', 'due_date',
                       'amount_due', 'amount_paid', 'paid_on', 'status')
    can_delete      = False
    show_change_link = True


class BookingInline(admin.TabularInline):
    model            = Booking
    extra            = 0
    readonly_fields  = ('plot', 'payment_plan', 'total_price', 'down_payment',
                        'status', 'booking_date', 'created_at')
    can_delete       = False
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display    = ('full_name', 'cnic', 'phone', 'customer_type', 'is_deleted', 'created_at')
    list_filter     = ('customer_type', 'is_deleted')
    search_fields   = ('full_name', 'cnic', 'phone')
    ordering        = ('full_name',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    inlines         = [BookingInline]

    def get_queryset(self, request):
        return Customer.all_objects.all()