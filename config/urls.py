# FILE: config/urls.py  (your ROOT_URLCONF)
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth: /accounts/login/  and  /accounts/logout/
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),

    # Dashboard (home after login)
    path("", include("apps.dashboard.urls", namespace="dashboard")),

    # Other apps
    path("projects/",  include("apps.projects_and_plots.urls", namespace="projects_and_plots")),
    path("customers/", include("apps.customers.urls",          namespace="customers")),
    path("bookings/",  include("apps.bookings.urls",           namespace="bookings")),
    path("expenses/",  include("apps.expenses.urls",           namespace="expenses")),
    path(
        "dashboard/",
        include("apps.dashboard.urls", namespace="dashboard"),
    ),  
]