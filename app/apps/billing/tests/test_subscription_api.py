# test_subscription_api.py

import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Subscription
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


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

    plan = PlanFactory(name="PRO")

    subscription = SubscriptionFactory(
        user=user,
        plan=plan,
        status=Subscription.STATUS.ACTIVE,
    )

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == subscription.id
    assert response.data["plan"] == plan.name
    assert response.data["status"] == Subscription.STATUS.ACTIVE
    assert response.data["cancel_at_period_end"] is False


@pytest.mark.django_db
def test_current_subscription_returns_null_when_user_has_no_subscription(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data is None


@pytest.mark.django_db
def test_current_subscription_ignores_non_active_subscription(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    SubscriptionFactory(
        user=user,
        status=Subscription.STATUS.CANCELED,
    )

    response = api_client.get(reverse("app.apps.billing:current-subscription"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data is None
