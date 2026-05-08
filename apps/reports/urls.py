"""
apps/reports/urls.py

All report URLs are staff-only (enforced in views via @staff_member_required).
Every view returns an Excel file as an attachment.

Overall reports    →  /reports/<slug>/
Project reports    →  /reports/project/<pk>/<slug>/
Customer reports   →  /reports/customer/<pk>/<slug>/
"""

from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    # ── Overall ────────────────────────────────────────────────────
    path(
        "monthly-collection/",
        views.monthly_collection,
        name="monthly_collection",
    ),
    path(
        "overdue-aging/",
        views.overdue_aging,
        name="overdue_aging",
    ),
    path(
        "payment-plan-breakdown/",
        views.payment_plan_breakdown,
        name="payment_plan_breakdown",
    ),
    # ── NEW ────────────────────────────────────────────────────────
    path(
        "cash-flow/",
        views.cash_flow,
        name="cash_flow",
    ),
    path(
        "token-pipeline/",
        views.token_pipeline,
        name="token_pipeline",
    ),

    # ── Per-project ────────────────────────────────────────────────
    path(
        "project/<int:pk>/plot-inventory/",
        views.project_plot_inventory,
        name="project_plot_inventory",
    ),
    path(
        "project/<int:pk>/revenue/",
        views.project_revenue,
        name="project_revenue",
    ),
    path(
        "project/<int:pk>/expenses/",
        views.project_expenses,
        name="project_expenses",
    ),
    path(
        "project/<int:pk>/per-plot-detail/",
        views.project_per_plot_detail,
        name="project_per_plot_detail",
    ),

    # ── Per-customer ───────────────────────────────────────────────
    path(
        "customer/<int:pk>/statement/",
        views.customer_statement,
        name="customer_statement",
    ),
]