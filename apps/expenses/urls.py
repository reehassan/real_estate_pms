from django.urls import path
from django.http import HttpResponse

app_name = "expenses"

def placeholder(request):
    return HttpResponse("Expenses page (coming soon)")

urlpatterns = [
    path("", placeholder, name="list"),
]