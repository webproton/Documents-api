import pytest
from apps.accounts.tests.factories import UserFactory
from rest_framework.test import APIClient

from app.apps.billing.models import Plan


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture(autouse=True)
def disable_celery_tasks(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True


@pytest.fixture(autouse=True)
def create_default_plans(db):
    Plan.objects.get_or_create(
        name=Plan.NAME.FREE,
        defaults={
            "description": "Free plan",
            "document_limit": 5,
            "price": 0,
            "is_active": True,
        },
    )


@pytest.fixture(autouse=True)
def stripe_settings(settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
