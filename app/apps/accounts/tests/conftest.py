import pytest
from apps.accounts.tests.factories import UserFactory
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()
