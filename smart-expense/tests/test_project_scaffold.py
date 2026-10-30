
from importlib import import_module

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import models

PROJECT_APPS = (
    "accounts",
    "categories",
    "transactions",
    "budgets",
    "alerts",
    "dashboard",
    "reports",
    "adminpanel",
    "audit",
)


@pytest.mark.parametrize("app_name", PROJECT_APPS)
def test_project_app_is_registered(app_name):
    assert app_name in settings.INSTALLED_APPS
    assert apps.get_app_config(app_name).name == app_name


@pytest.mark.parametrize("app_name", PROJECT_APPS)
def test_project_app_has_migrations_package(app_name):
    migration_package = import_module(f"{app_name}.migrations")
    assert migration_package.__file__ is not None


def test_custom_user_model_is_configured():
    user_model = get_user_model()

    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert user_model.__name__ == "User"
    assert issubclass(user_model, AbstractUser)
    assert user_model.REQUIRED_FIELDS == ["email"]


def test_custom_user_email_has_unique_constraints():
    user_model = get_user_model()
    email_field = user_model._meta.get_field("email")

    assert isinstance(email_field, models.EmailField)
    assert email_field.unique

    assert any(
        isinstance(constraint, models.UniqueConstraint)
        and constraint.name == "user_email_case_unique"
        for constraint in user_model._meta.constraints
    )


@pytest.mark.parametrize(
    ("setting_name", "expected_path"),
    [
        ("ASGI_APPLICATION", "config.asgi.application"),
        ("WSGI_APPLICATION", "config.wsgi.application"),
    ],
)
def test_server_application_entry_points_are_importable(
    setting_name, expected_path
):
    application_path = getattr(settings, setting_name)

    assert application_path == expected_path

    module_path, _, attribute_name = application_path.rpartition(".")
    application = getattr(import_module(module_path), attribute_name)

    assert callable(application)
