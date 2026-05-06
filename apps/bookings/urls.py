from django.urls import path
from apps.bookings.views import installment_receipt

urlpatterns = [
    path("admin/bookings/receipt/<int:installment_id>/", installment_receipt, name="installment_receipt"),
]