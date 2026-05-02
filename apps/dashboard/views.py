# FILE: apps/dashboard/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard. LoginRequiredMixin redirects unauthenticated users
    to settings.LOGIN_URL (i.e. /accounts/login/?next=/) automatically.
    """
    template_name = "dashboard/index.html"