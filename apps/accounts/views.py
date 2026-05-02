# FILE: apps/accounts/views.py
"""
Wire Django's auth views — nothing extra needed here;
we just re-export them with the right names so urls.py stays clean.
"""
from django.contrib.auth.views import LoginView, LogoutView  # noqa: F401

# If you ever need a custom login (e.g. to log events), subclass here:
class RoyalLoginView(LoginView):
    template_name = "registration/login.html"
