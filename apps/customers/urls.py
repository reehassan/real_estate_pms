from django.urls import path
from django.http import HttpResponse

app_name = "customers"

def placeholder(request):
    return HttpResponse("Customers page (coming soon)")

urlpatterns = [
    path("", placeholder, name="list"),
]