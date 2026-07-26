# app/apps/billing/tests/test_checkout_api.py
from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException

from app.apps.billing.models import Plan
from app.apps.billing.tests.factories.plan import PlanFactory


@pytest.mark.django_db
def test_checkout_requires_authentication(api_client):
    plan = PlanFactory(name=Plan.NAME.PRO)

    response = api_client.post(
        reverse("app.apps.billing:checkout"), {"plan": plan.id}, format="json"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_checkout_returns_400_for_unknown_plan(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.post(
        reverse("app.apps.billing:checkout"), {"plan": 999}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "plan" in response.data["errors"]


@pytest.mark.django_db
def test_checkout_rejects_free_plan(api_client, user):
    api_client.force_authenticate(user)

    plan = Plan.objects.get(name=Plan.NAME.FREE)

    response = api_client.post(
        reverse("app.apps.billing:checkout"),
        {"plan": plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errors"]["plan"][0] == "The FREE plan cannot be purchased."


@pytest.mark.django_db
@patch("app.apps.billing.views.checkout.StripeService.start_checkout")
def test_checkout_returns_checkout_url(
    mock_start_checkout,
    api_client,
    user,
):
    api_client.force_authenticate(user)

    plan = PlanFactory(name=Plan.NAME.PRO)

    session = Mock()
    session.id = "cs_test_123"
    session.url = "https://checkout.stripe.com/test"

    mock_start_checkout.return_value = session

    response = api_client.post(
        reverse("app.apps.billing:checkout"),
        {"plan": plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "checkout_url": "https://checkout.stripe.com/test",
        "session_id": "cs_test_123",
    }

    mock_start_checkout.assert_called_once_with(
        user=user,
        plan=plan,
    )


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.StripeService.start_checkout")
def test_checkout_returns_error_when_stripe_service_fails(
    mock_start_checkout,
    api_client,
    user,
):
    api_client.force_authenticate(user)

    plan = PlanFactory(name=Plan.NAME.PRO)

    mock_start_checkout.side_effect = APIException("Stripe error")

    response = api_client.post(
        reverse("app.apps.billing:checkout"),
        {
            "plan": plan.id,
            "session_id": "cs_test_123",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
