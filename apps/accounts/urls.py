from django.urls import path
from apps.accounts.views import RoyalLoginView
from django.contrib.auth.views import LogoutView


app_name = "accounts"


urlpatterns = [
    path("login/", RoyalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]