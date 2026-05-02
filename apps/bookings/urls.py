from django.urls import path
from django.http import HttpResponse

app_name = "bookings"

def placeholder(request):
    return HttpResponse("Bookings page (coming soon)")

urlpatterns = [
    path("", placeholder, name="list"),
]