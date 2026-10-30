
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from categories.models import Category
from transactions.models import Transaction

pytestmark = pytest.mark.django_db


def test_authenticated_navigation_shows_all_application_sections(auth):
    response = auth.get(reverse("dashboard:home"))

    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Categories" in response.content
    assert b"Transactions" in response.content
    assert b"Budgets" in response.content
    assert b"Reports" in response.content
    assert b"Signed in as alice" in response.content
    assert b"Log out" in response.content


def test_guest_navigation_shows_login_and_register(client):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert b"Login" in response.content
    assert b"Register" in response.content
    assert b"Transactions" not in response.content


def test_authenticated_navigation_marks_current_page(auth):
    response = auth.get(reverse("dashboard:home"))

    assert b'aria-current="page"' in response.content


def test_invalid_login_displays_accessible_error_summary(client, user):
    response = client.post(
        reverse("accounts:login"),
        {
            "username": user.username,
            "password": "Incorrect-Password-2026!",
        },
    )

    assert response.status_code == 200
    assert b"Please correct the following errors" in response.content
    assert b'role="alert"' in response.content


def test_invalid_registration_uses_shared_error_summary(client):
    response = client.post(
        reverse("accounts:register"),
        {
            "username": "newuser",
            "email": "invalid-email",
            "password1": "Strong-Test-Password-2026!",
            "password2": "Strong-Test-Password-2026!",
        },
    )

    assert response.status_code == 200
    assert b"Please correct the following errors" in response.content
    assert b"email" in response.content.lower()
    assert b'href="#id_email"' in response.content


def test_category_protection_message_uses_accessible_message_pattern(
    auth, user, category
):
    Transaction.objects.create(
        owner=user,
        category=category,
        kind=Category.EXPENSE,
        amount=Decimal("250.00"),
        date=date(2026, 10, 30),
        description="Protected category test",
    )

    response = auth.post(
        reverse("categories:delete", args=[category.pk]),
        follow=True,
    )

    assert response.status_code == 200
    assert b"This category is used by a transaction or budget" in response.content
    assert b'role="alert"' in response.content
    assert b"message--error" in response.content
