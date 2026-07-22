# apps/billing/tests/test_subscription_api.py

import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory


@pytest.mark.django_db
def test_current_subscription_requires_authentication(api_client):
    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_current_subscription_returns_active_subscription(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    plan = PlanFactory(name=Plan.NAME.PRO)

    subscription = user.subscription
    subscription.plan = plan
    subscription.status = Subscription.STATUS.ACTIVE
    subscription.save(update_fields=["plan", "status"])

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == subscription.id
    assert response.data["plan"]["id"] == plan.id
    assert response.data["plan"]["name"] == plan.name
    assert response.data["status"] == Subscription.STATUS.ACTIVE
    assert response.data["cancel_at_period_end"] is False


@pytest.mark.django_db
def test_current_subscription_returns_free_subscription(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == user.subscription.id

    assert response.data["plan"]["name"] == Plan.NAME.FREE
    assert response.data["status"] == Subscription.STATUS.ACTIVE
    assert response.data["cancel_at_period_end"] is False


@pytest.mark.django_db
def test_current_subscription_ignores_non_active_subscription(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    subscription = user.subscription
    subscription.status = Subscription.STATUS.CANCELED
    subscription.save(update_fields=["status"])

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data is None
