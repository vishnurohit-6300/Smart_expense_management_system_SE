from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from budgets.models import Budget
from categories.models import Category
from transactions.models import Transaction

pytestmark = pytest.mark.django_db


def add_transaction(owner, category, amount, day, description="test transaction"):
    return Transaction.objects.create(
        owner=owner,
        category=category,
        kind=category.kind,
        amount=Decimal(str(amount)),
        date=date(2026, 10, day),
        description=description,
    )


def get_dashboard(client):
    return client.get(reverse("dashboard:home"))


def test_dashboard_totals_match_transaction_records(auth, user, category):
    income_category = Category.objects.create(owner=user, name="Salary", kind=Category.INCOME)
    add_transaction(user, income_category, "30000.00", 1, "October salary")
    add_transaction(user, income_category, "5000.00", 10, "Freelance")
    add_transaction(user, category, "4500.00", 12, "Groceries")
    add_transaction(user, category, "1500.00", 20, "Transport")

    response = get_dashboard(auth)

    assert response.status_code == 200
    assert response.context["income"] == Decimal("35000.00")
    assert response.context["expense"] == Decimal("6000.00")
    assert response.context["balance"] == Decimal("29000.00")


def test_empty_dashboard_returns_zero_totals_and_empty_lists(auth):
    response = get_dashboard(auth)

    assert response.status_code == 200
    assert response.context["income"] == Decimal("0.00")
    assert response.context["expense"] == Decimal("0.00")
    assert response.context["balance"] == Decimal("0.00")
    assert list(response.context["recent"]) == []
    assert list(response.context["budgets"]) == []


def test_income_only_dashboard_uses_zero_expenses(auth, user):
    income_category = Category.objects.create(owner=user, name="Salary only", kind=Category.INCOME)
    add_transaction(user, income_category, "12000.00", 5, "Salary")

    response = get_dashboard(auth)

    assert response.context["income"] == Decimal("12000.00")
    assert response.context["expense"] == Decimal("0.00")
    assert response.context["balance"] == Decimal("12000.00")


def test_expense_only_dashboard_uses_zero_income(auth, user, category):
    add_transaction(user, category, "350.00", 8, "Lunch")

    response = get_dashboard(auth)

    assert response.context["income"] == Decimal("0.00")
    assert response.context["expense"] == Decimal("350.00")
    assert response.context["balance"] == Decimal("-350.00")


def test_dashboard_excludes_other_users_transactions(auth, user, other, category):
    other_category = Category.objects.create(owner=other, name="Private food", kind=Category.EXPENSE)
    add_transaction(user, category, "100.00", 10, "My expense")
    add_transaction(other, other_category, "9000.00", 11, "Another user's expense")

    response = get_dashboard(auth)

    assert response.context["expense"] == Decimal("100.00")
    assert [item.description for item in response.context["recent"]] == ["My expense"]


def test_dashboard_shows_only_ten_most_recent_transactions(auth, user, category):
    for day in range(1, 13):
        add_transaction(user, category, day * 10, day, f"transaction-{day}")

    response = get_dashboard(auth)
    recent = list(response.context["recent"])

    assert len(recent) == 10
    assert recent[0].description == "transaction-12"
    assert recent[-1].description == "transaction-3"
    assert all(recent[index].date >= recent[index + 1].date for index in range(9))


def test_dashboard_shows_only_logged_in_users_budgets(auth, user, other, category):
    own_budget = Budget.objects.create(
        owner=user,
        category=category,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        limit=Decimal("1000.00"),
    )
    other_category = Category.objects.create(owner=other, name="Other food", kind=Category.EXPENSE)
    Budget.objects.create(
        owner=other,
        category=other_category,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        limit=Decimal("2000.00"),
    )

    response = get_dashboard(auth)
    budgets = list(response.context["budgets"])

    assert [budget.pk for budget in budgets] == [own_budget.pk]


def test_dashboard_displays_budget_progress_and_warning(auth, user, category):
    budget = Budget.objects.create(
        owner=user,
        category=category,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        limit=Decimal("1000.00"),
        threshold=80,
    )
    add_transaction(user, category, "800.00", 20, "Budget threshold reached")

    response = get_dashboard(auth)

    assert budget.spent == Decimal("800.00")
    assert budget.progress == Decimal("80.0")
    assert budget.status == "Warning"
    assert b"Warning" in response.content


def test_dashboard_totals_update_after_create_edit_and_delete(auth, user, category):
    item = add_transaction(user, category, "250.00", 10, "Initial expense")
    assert get_dashboard(auth).context["expense"] == Decimal("250.00")

    item.amount = Decimal("400.00")
    item.save(update_fields=["amount"])
    assert get_dashboard(auth).context["expense"] == Decimal("400.00")

    item.delete()
    assert get_dashboard(auth).context["expense"] == Decimal("0.00")

def test_dashboard_requires_login(client):
    response = get_dashboard(client)

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_dashboard_reflects_transaction_create_edit_delete_requests(
    auth, user, category
):
    create_response = auth.post(
        reverse("transactions:new"),
        {
            "kind": Category.EXPENSE,
            "category": category.pk,
            "amount": "250.00",
            "date": "2026-10-10",
            "description": "Integration test expense",
        },
    )

    assert create_response.status_code == 302

    item = Transaction.objects.get(
        owner=user,
        description="Integration test expense",
    )
    assert get_dashboard(auth).context["expense"] == Decimal("250.00")

    edit_response = auth.post(
        reverse("transactions:edit", args=[item.pk]),
        {
            "kind": Category.EXPENSE,
            "category": category.pk,
            "amount": "400.00",
            "date": "2026-10-10",
            "description": "Updated integration expense",
        },
    )

    assert edit_response.status_code == 302
    assert get_dashboard(auth).context["expense"] == Decimal("400.00")

    delete_response = auth.post(
        reverse("transactions:delete", args=[item.pk])
    )

    assert delete_response.status_code == 302
    assert not Transaction.objects.filter(pk=item.pk).exists()
    assert get_dashboard(auth).context["expense"] == Decimal("0.00")
