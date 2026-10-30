from datetime import date
from decimal import Decimal

import pytest

from budgets.models import Budget
from categories.models import Category
from dashboard.services import get_dashboard_data
from transactions.models import Transaction

pytestmark = pytest.mark.django_db


def create_transaction(owner, category, amount, transaction_date, description):
    return Transaction.objects.create(
        owner=owner,
        category=category,
        kind=category.kind,
        amount=Decimal(str(amount)),
        date=transaction_date,
        description=description,
    )


def create_budget(owner, category, limit="1000.00", threshold=80):
    return Budget.objects.create(
        owner=owner,
        category=category,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        limit=Decimal(str(limit)),
        threshold=threshold,
    )


def test_dashboard_financial_summary_excludes_other_users(
    user, other, category
):
    salary = Category.objects.create(
        owner=user,
        name="Salary",
        kind=Category.INCOME,
    )
    other_category = Category.objects.create(
        owner=other,
        name="Other Food",
        kind=Category.EXPENSE,
    )

    create_transaction(
        user, salary, "30000.00", date(2026, 10, 1), "Salary"
    )
    create_transaction(
        user, category, "5000.00", date(2026, 10, 5), "Groceries"
    )
    create_transaction(
        other, other_category, "9000.00", date(2026, 10, 6), "Private expense"
    )

    result = get_dashboard_data(user)

    assert result["income"] == Decimal("30000.00")
    assert result["expense"] == Decimal("5000.00")
    assert result["balance"] == Decimal("25000.00")
    assert len(result["recent"]) == 2


def test_dashboard_returns_only_ten_most_recent_transactions(user, category):
    for day in range(1, 13):
        create_transaction(
            user,
            category,
            day * 100,
            date(2026, 10, day),
            f"Transaction {day}",
        )

    result = get_dashboard_data(user)
    recent = list(result["recent"])

    assert len(recent) == 10
    assert recent[0].description == "Transaction 12"
    assert recent[-1].description == "Transaction 3"


def test_budget_spending_respects_budget_date_range(user, category):
    create_budget(user, category)

    create_transaction(
        user, category, "350.00", date(2026, 10, 10), "Inside period"
    )
    create_transaction(
        user, category, "200.00", date(2026, 9, 30), "Before period"
    )
    create_transaction(
        user, category, "400.00", date(2026, 11, 1), "After period"
    )

    result = get_dashboard_data(user)
    budget = result["budgets"][0]

    assert budget["spent"] == Decimal("350.00")
    assert budget["progress"] == Decimal("35.0")
    assert budget["status"] == "On track"


def test_budget_progress_rounding_does_not_trigger_early_warning(
    user, category
):
    create_budget(user, category)

    create_transaction(
        user, category, "799.99", date(2026, 10, 15), "Below threshold"
    )

    result = get_dashboard_data(user)
    budget = result["budgets"][0]

    assert budget["progress"] == Decimal("80.0")
    assert budget["status"] == "On track"


def test_budget_status_becomes_warning_at_exact_threshold(user, category):
    create_budget(user, category, threshold=80)

    create_transaction(
        user, category, "800.00", date(2026, 10, 15), "Threshold reached"
    )

    result = get_dashboard_data(user)
    budget = result["budgets"][0]

    assert budget["progress"] == Decimal("80.0")
    assert budget["status"] == "Warning"


def test_exceeded_budget_caps_progress_bar_at_one_hundred(
    user, category
):
    create_budget(user, category)

    create_transaction(
        user, category, "1200.00", date(2026, 10, 15), "Over budget"
    )

    result = get_dashboard_data(user)
    budget = result["budgets"][0]

    assert budget["spent"] == Decimal("1200.00")
    assert budget["progress"] == Decimal("120.0")
    assert budget["progress_bar"] == Decimal("100")
    assert budget["status"] == "Exceeded"


def test_budget_without_expenses_returns_zero_progress(user, category):
    create_budget(user, category)

    result = get_dashboard_data(user)
    budget = result["budgets"][0]

    assert budget["spent"] == Decimal("0.00")
    assert budget["progress"] == Decimal("0.0")
    assert budget["progress_bar"] == Decimal("0")
    assert budget["status"] == "On track"


def test_dashboard_includes_only_current_users_budgets(
    user, other, category
):
    own_budget = create_budget(user, category)

    other_category = Category.objects.create(
        owner=other,
        name="Other Category",
        kind=Category.EXPENSE,
    )
    create_budget(other, other_category, limit="2000.00")

    result = get_dashboard_data(user)

    assert len(result["budgets"]) == 1
    assert result["budgets"][0]["category"] == own_budget.category.name
