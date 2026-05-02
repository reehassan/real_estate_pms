from django.urls import path
from django.http import HttpResponse

app_name = "projects_and_plots"

def placeholder(request):
    return HttpResponse("Projects and Plots page (coming soon)")

urlpatterns = [
    path("", placeholder, name="list"),
]