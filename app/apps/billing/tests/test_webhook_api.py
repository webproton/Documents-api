# app/apps/billing/tests/test_webhook_api.py

from unittest.mock import patch

import pytest
import stripe
from django.urls import reverse
from rest_framework import status


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
