# app/apps/billing/tests/test_cancel_subscription_api.py
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory


def _set_subscription(user, **fields):
    updated = Subscription.objects.filter(user=user).update(**fields)
    assert updated == 1, "Subscription row was not found/updated for user"
    return Subscription.objects.get(user=user)


@pytest.mark.django_db
def test_cancel_subscription_requires_authentication(api_client):
    response = api_client.post(reverse("app.apps.billing:cancel-subscription"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@patch(
    "app.apps.billing.serializers.cancel_subscription.StripeService.cancel_subscription"
)
def test_cancel_subscription_success(mock_cancel, api_client, user):
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    subscription = _set_subscription(
        user,
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        stripe_subscription_id="sub_123",
    )
    api_client.force_authenticate(user)

    mock_cancel.return_value = subscription

    response = api_client.post(reverse("app.apps.billing:cancel-subscription"))

    assert response.status_code == status.HTTP_200_OK
    mock_cancel.assert_called_once()


@pytest.mark.django_db
def test_cancel_subscription_no_active_subscription_returns_400(api_client, user):
    _set_subscription(user, status=Subscription.STATUS.CANCELED)
    api_client.force_authenticate(user)

    response = api_client.post(reverse("app.apps.billing:cancel-subscription"))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cancel_subscription_free_plan_without_stripe_id_returns_400(api_client, user):
    """The FREE plan, stripe_subscription_id is empty, there's nothing to cancel."""
    _set_subscription(
        user,
        status=Subscription.STATUS.ACTIVE,
        stripe_subscription_id=None,
    )
    api_client.force_authenticate(user)

    response = api_client.post(reverse("app.apps.billing:cancel-subscription"))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
