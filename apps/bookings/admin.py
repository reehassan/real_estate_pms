from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Booking, Installment
from apps.projects_and_plots.models import Plot


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
        return Booking.all_objects.select_related('customer', 'plot')

    def save_model(self, request, obj, form, change):
        # Use row-level locking to prevent races when multiple admins
        # try to book the same plot concurrently.
        if not change:
            with transaction.atomic():
                plot = Plot.objects.select_for_update().get(pk=obj.plot_id)
                if plot.status != Plot.Status.AVAILABLE:
                    raise ValidationError({'plot': 'Plot must be AVAILABLE to create a booking.'})

                # Pre-mark the plot as booked to reduce chance of uniqueness violations.
                # Guard: if the booking is created as CANCELLED, don't reserve the plot.
                if obj.status != Booking.Status.CANCELLED:
                    plot.status = Plot.Status.BOOKED
                    plot.save(update_fields=["status"])

                super().save_model(request, obj, form, change)
        else:
            super().save_model(request, obj, form, change)


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):

    list_display    = ('challan_number', 'booking', 'installment_number',
                       'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter     = ('status',)
    search_fields   = ('challan_number', 'booking__customer__full_name')
    ordering        = ('due_date', 'installment_number')
    readonly_fields = ('challan_number', 'installment_number', 'due_date',
                       'amount_due', 'created_at')