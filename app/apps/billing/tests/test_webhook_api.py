# app/apps/billing/tests/test_webhook_api.py

from unittest.mock import patch

import pytest
import stripe
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app.apps.billing.models import Order, Plan, Subscription
from app.apps.billing.tests.factories.order import OrderFactory
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


@pytest.mark.django_db
@patch("app.apps.billing.views.webhook.StripeWebhookService.process")
@patch("app.apps.billing.views.webhook.stripe.Webhook.construct_event")
def test_webhook_success(
    mock_construct_event,
    mock_process,
    api_client,
):
    event = {
        "id": "evt_test",
        "type": "invoice.paid",
    }

    mock_construct_event.return_value = event

    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="signature",
    )

    assert response.status_code == status.HTTP_200_OK

    mock_construct_event.assert_called_once()
    mock_process.assert_called_once_with(event)


@pytest.mark.django_db
def test_webhook_requires_signature(api_client):
    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"{}",
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Missing Stripe-Signature header."


@pytest.mark.django_db
@patch("app.apps.billing.views.webhook.stripe.Webhook.construct_event")
def test_webhook_invalid_payload(
    mock_construct_event,
    api_client,
):
    mock_construct_event.side_effect = ValueError

    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"invalid",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="signature",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Invalid payload."


@pytest.mark.django_db
@patch("app.apps.billing.views.webhook.stripe.Webhook.construct_event")
def test_webhook_invalid_signature(
    mock_construct_event,
    api_client,
):
    mock_construct_event.side_effect = stripe.error.SignatureVerificationError(
        "invalid",
        "signature",
    )

    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="signature",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Invalid Stripe signature."


@pytest.mark.django_db
@patch("app.apps.billing.views.webhook.stripe.Webhook.construct_event")
def test_webhook_invoice_paid_end_to_end_updates_subscription_and_order(
    mock_construct_event,
    api_client,
):
    """
    Full chain: view → StripeWebhookService.process → handler → DB.
    Does NOT mock process() itself, to catch routing/wiring bugs that
    isolated service tests wouldn't see.
    """
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.PENDING,
        plan=Plan.objects.get(name=Plan.NAME.FREE),
    )
    order = OrderFactory(
        subscription=subscription,
        plan=pro_plan,
        status=Order.STATUS.PENDING,
    )

    event = {
        "id": "evt_test",
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": "sub_test",
                "customer": "cus_test",
                "id": "in_test",
                "period_end": int(timezone.now().timestamp()) + 3600,
            }
        },
    }
    mock_construct_event.return_value = event

    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="signature",
    )

    assert response.status_code == status.HTTP_200_OK

    subscription.refresh_from_db()
    order.refresh_from_db()

    assert subscription.status == Subscription.STATUS.ACTIVE
    assert subscription.plan == pro_plan
    assert order.status == Order.STATUS.PAID


@pytest.mark.django_db
@patch("app.apps.billing.views.webhook.stripe.Webhook.construct_event")
def test_webhook_returns_200_even_when_no_matching_subscription(
    mock_construct_event,
    api_client,
):
    """
    An event referencing a subscription we don't have locally must not
    crash the endpoint with a 500 — it should be logged and acknowledged.
    """
    event = {
        "id": "evt_orphan",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": "sub_does_not_exist",
                "id": "in_orphan",
            }
        },
    }
    mock_construct_event.return_value = event

    response = api_client.post(
        reverse("app.apps.billing:webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="signature",
    )

    assert response.status_code == status.HTTP_200_OK
