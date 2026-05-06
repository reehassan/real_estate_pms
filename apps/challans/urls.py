# apps/challans/urls.py

from django.urls import path
from . import views

app_name = 'challans'

urlpatterns = [
    path('<int:installment_id>/pdf/', views.challan_pdf, name='pdf'),
]