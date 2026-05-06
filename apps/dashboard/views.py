"""
apps/dashboard/views.py

Unfold dashboard callback — wired via UNFOLD["DASHBOARD_CALLBACK"].
No URL needed. Add to INSTALLED_APPS and point the setting here.

Settings changes required (config/settings/base.py):
  1. Add "apps.dashboard" to INSTALLED_APPS
  2. Add to UNFOLD dict:
         "DASHBOARD_CALLBACK": "apps.dashboard.views.dashboard_callback",
"""

import json
from datetime import date, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.bookings.models import Booking, Installment
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.projects_and_plots.models import Plot, Project


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def _last_12_months() -> list[date]:
    """Return the first day of each of the last 12 months, oldest first."""
    today = timezone.localdate()
    months = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))
    return months


# ──────────────────────────────────────────────────────────────
# CALLBACK
# ──────────────────────────────────────────────────────────────

def dashboard_callback(request, context: dict) -> dict:
    today  = timezone.localdate()
    months = _last_12_months()

    # ── KPI Row 1: Money ──────────────────────────────────────
    total_collected = (
        Installment.objects
        .filter(status="paid")
        .aggregate(t=Sum("amount_paid"))["t"] or 0
    )

    outstanding = (
        Installment.objects
        .filter(status__in=["pending", "overdue"])
        .aggregate(t=Sum(F("amount_due") - F("amount_paid")))["t"] or 0
    )

    this_month_collected = (
        Installment.objects
        .filter(status="paid", paid_on__year=today.year, paid_on__month=today.month)
        .aggregate(t=Sum("amount_paid"))["t"] or 0
    )

    expenses_this_month = (
        Expense.objects
        .filter(date__year=today.year, date__month=today.month)
        .aggregate(t=Sum("amount"))["t"] or 0
    )

    # ── KPI Row 2: Operations ─────────────────────────────────
    active_bookings = Booking.objects.filter(status="active").count()

    plot_counts = Plot.objects.values("status").annotate(n=Count("id"))
    plot_map    = {p["status"]: p["n"] for p in plot_counts}
    available_plots = plot_map.get("AVAILABLE", 0)
    booked_plots    = plot_map.get("BOOKED", 0) + plot_map.get("SOLD", 0)
    total_plots     = sum(plot_map.values())

    overdue_qs     = Installment.objects.filter(status="overdue")
    overdue_count  = overdue_qs.count()
    overdue_amount = (
        overdue_qs
        .aggregate(t=Sum(F("amount_due") - F("amount_paid")))["t"] or 0
    )

    due_in_7 = (
        Installment.objects
        .filter(status="pending", due_date__gte=today, due_date__lte=today + timedelta(days=7))
        .count()
    )

    new_customers = Customer.objects.filter(
        created_at__year=today.year,
        created_at__month=today.month,
    ).count()

    totals = Installment.objects.aggregate(due=Sum("amount_due"), paid=Sum("amount_paid"))
    collection_rate = round(
        float(totals["paid"] or 0) / float(totals["due"] or 1) * 100, 1
    )

    # ── Revenue vs Expense chart (last 12 months) ─────────────
    raw_revenue = dict(
        Installment.objects
        .filter(status="paid", paid_on__isnull=False, paid_on__gte=months[0])
        .annotate(month=TruncMonth("paid_on"))
        .values("month")
        .annotate(t=Sum("amount_paid"))
        .values_list("month", "t")
    )
    raw_expenses = dict(
        Expense.objects
        .filter(date__gte=months[0])
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(t=Sum("amount"))
        .values_list("month", "t")
    )

    chart_labels   = [m.strftime("%b %Y") for m in months]
    revenue_data   = [float(raw_revenue.get(m, 0)) for m in months]
    expense_data   = [float(raw_expenses.get(m, 0)) for m in months]

    # ── Plot status donut ─────────────────────────────────────
    status_order  = ["AVAILABLE", "TOKEN", "BOOKED", "SOLD"]
    status_labels = ["Available", "Token", "Booked", "Sold"]
    status_colors = ["#16a34a", "#d97706", "#2563eb", "#7c3aed"]
    status_data   = [plot_map.get(s, 0) for s in status_order]

    # ── Expense by category (this month) ─────────────────────
    cat_qs = (
        Expense.objects
        .filter(date__year=today.year, date__month=today.month)
        .values("category")
        .annotate(t=Sum("amount"))
        .order_by("-t")
    )
    cat_labels = [c["category"].title() for c in cat_qs]
    cat_data   = [float(c["t"]) for c in cat_qs]

    # ── Recent bookings table ─────────────────────────────────
    recent_bookings = (
        Booking.objects
        .select_related("customer", "plot", "plot__project")
        .order_by("-created_at")[:8]
    )

    # ── Overdue installments table ────────────────────────────
    overdue_list = (
        Installment.objects
        .filter(status="overdue")
        .select_related("booking__customer", "booking__plot", "booking__plot__project")
        .order_by("due_date")[:8]
    )

    # ── Upcoming (next 7 days) ────────────────────────────────
    upcoming_list = (
        Installment.objects
        .filter(status="pending", due_date__gte=today, due_date__lte=today + timedelta(days=7))
        .select_related("booking__customer", "booking__plot")
        .order_by("due_date")[:8]
    )

    context.update({
        # KPIs
        "total_collected":      total_collected,
        "outstanding":          outstanding,
        "this_month_collected": this_month_collected,
        "expenses_this_month":  expenses_this_month,
        "active_bookings":      active_bookings,
        "available_plots":      available_plots,
        "booked_plots":         booked_plots,
        "total_plots":          total_plots,
        "overdue_count":        overdue_count,
        "overdue_amount":       overdue_amount,
        "due_in_7":             due_in_7,
        "new_customers":        new_customers,
        "collection_rate":      collection_rate,
        # Charts — JSON strings, safe to drop into <script>
        "chart_labels":         json.dumps(chart_labels),
        "revenue_data":         json.dumps(revenue_data),
        "expense_data":         json.dumps(expense_data),
        "plot_status_labels":   json.dumps(status_labels),
        "plot_status_data":     json.dumps(status_data),
        "plot_status_colors":   json.dumps(status_colors),
        "cat_labels":           json.dumps(cat_labels),
        "cat_data":             json.dumps(cat_data),
        # Tables
        "recent_bookings":  recent_bookings,
        "overdue_list":     overdue_list,
        "upcoming_list":    upcoming_list,
        "today":            today,
    })
    return context