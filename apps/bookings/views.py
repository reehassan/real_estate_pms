# apps/bookings/views.py  
from django.shortcuts import render
from django.db import transaction
from .models import Booking
from .utils import generate_installments

# def create_booking(request):
#     with transaction.atomic():
#         booking = Booking.objects.create(
#             customer     = customer,
#             plot         = plot,
#             booked_by    = request.user,
#             total_price  = total_price,
#             down_payment = down_payment,
#             payment_plan = payment_plan,
#         )
#         generate_installments(booking)