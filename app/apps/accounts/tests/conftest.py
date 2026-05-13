import pytest
from apps.accounts.tests.factories import UserFactory
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture(autouse=True)
def disable_celery_tasks(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = False
