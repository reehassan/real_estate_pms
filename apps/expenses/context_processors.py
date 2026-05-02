# FILE: apps/expenses/context_processors.py
"""
Injects `pending_expenses_count` into every template context so the
sidebar badge stays up-to-date automatically on every page load.
"""
from apps.expenses.models import Expense


def pending_expenses_count(request):
    """Return count of pending expenses for authenticated users only."""
    if not request.user.is_authenticated:
        return {"pending_expenses_count": 0}
    count = Expense.objects.filter(status="pending").count()
    return {"pending_expenses_count": count}