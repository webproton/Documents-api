# app/apps/billing/tests/test_change_plan_api.py
from unittest.mock import Mock, patch

import pytest
import stripe
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.services.stripe import StripeService
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


def _set_subscription(user, **fields):
    Subscription.objects.filter(user=user).update(**fields)
    user.refresh_from_db()
    return user.subscription


@pytest.mark.django_db
def test_change_plan_requires_authentication(api_client):
    plan = PlanFactory(name=Plan.NAME.PRO)

    response = api_client.post(
        reverse("app.apps.billing:change-plan"), {"plan": plan.id}, format="json"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_change_plan_rejects_free_plan(api_client, user):
    api_client.force_authenticate(user)
    free_plan = Plan.objects.get(name=Plan.NAME.FREE)

    response = api_client.post(
        reverse("app.apps.billing:change-plan"),
        {"plan": free_plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errors"]["plan"][0] == "The FREE plan cannot be purchased."


@pytest.mark.django_db
def test_change_plan_rejects_same_plan(api_client, user):
    pro_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")
    _set_subscription(
        user,
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        stripe_subscription_id="sub_123",
    )

    api_client.force_authenticate(user)

    response = api_client.post(
        reverse("app.apps.billing:change-plan"),
        {"plan": pro_plan.id},
        format="json",
        raise_request_exception=True,
    )
    print(response.json())

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already subscribed" in response.data["errors"]["plan"][0]


@pytest.mark.django_db
@patch("app.apps.billing.serializers.change_plan.StripeService.start_checkout")
def test_change_plan_without_stripe_subscription_falls_back_to_checkout(
    mock_start_checkout, api_client, user
):
    """
    First payment (no stripe_subscription_id yet)
    goes through checkout, not modify().
    """
    pro_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")
    api_client.force_authenticate(user)

    session = Mock(id="cs_test_123", url="https://checkout.stripe.com/test")
    mock_start_checkout.return_value = session

    response = api_client.post(
        reverse("app.apps.billing:change-plan"),
        {"plan": pro_plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["checkout_url"] == session.url
    mock_start_checkout.assert_called_once_with(user=user, plan=pro_plan)


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.modify")
@patch("app.apps.billing.services.stripe.stripe.Subscription.retrieve")
def test_change_plan_with_existing_subscription_calls_stripe_modify(
    mock_retrieve, mock_modify, api_client, user
):
    pro_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")
    business_plan = PlanFactory(
        name=Plan.NAME.BUSINESS, stripe_price_id="price_business"
    )
    _set_subscription(
        user,
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        stripe_subscription_id="sub_123",
    )
    api_client.force_authenticate(user)

    mock_retrieve.return_value = {"items": {"data": [{"id": "si_123"}]}}

    response = api_client.post(
        reverse("app.apps.billing:change-plan"),
        {"plan": business_plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    subscription = Subscription.objects.get(user=user)
    assert subscription.plan == business_plan
    mock_modify.assert_called_once_with(
        "sub_123",
        items=[{"id": "si_123", "price": "price_business"}],
        proration_behavior="create_prorations",
    )


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.retrieve")
def test_change_plan_returns_error_when_stripe_fails(mock_retrieve, api_client, user):
    pro_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")
    business_plan = PlanFactory(
        name=Plan.NAME.BUSINESS, stripe_price_id="price_business"
    )
    _set_subscription(
        user,
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        stripe_subscription_id="sub_123",
    )
    api_client.force_authenticate(user)

    mock_retrieve.side_effect = stripe.error.StripeError("boom")

    response = api_client.post(
        reverse("app.apps.billing:change-plan"),
        {"plan": business_plan.id},
        format="json",
    )

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.django_db
def test_change_plan_rejects_same_plan_at_service_level():
    """The protection should work even if the call didn't come from the view"""
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    pro_plan.stripe_price_id = "price_pro"
    pro_plan.save(update_fields=["stripe_price_id"])

    subscription = SubscriptionFactory(
        plan=pro_plan,
        stripe_subscription_id="sub_123",
    )

    with pytest.raises(APIException):
        StripeService.change_plan(subscription, pro_plan)


@pytest.mark.django_db
def test_change_plan_rejects_plan_without_stripe_price_id():
    """new_plan without stripe_price_id — Stripe cannot be called."""
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    pro_plan.stripe_price_id = "price_pro"
    pro_plan.save(update_fields=["stripe_price_id"])

    business_plan = PlanFactory(name=Plan.NAME.BUSINESS)
    business_plan.stripe_price_id = None
    business_plan.save(update_fields=["stripe_price_id"])

    subscription = SubscriptionFactory(
        plan=pro_plan,
        stripe_subscription_id="sub_123",
    )

    with pytest.raises(APIException):
        StripeService.change_plan(subscription, business_plan)


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.retrieve")
def test_change_plan_raises_when_stripe_subscription_has_no_items(mock_retrieve):
    """items.data == [] — no IndexError should fall, only APIException."""
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    pro_plan.stripe_price_id = "price_pro"
    pro_plan.save(update_fields=["stripe_price_id"])

    business_plan = PlanFactory(name=Plan.NAME.BUSINESS)
    business_plan.stripe_price_id = "price_business"
    business_plan.save(update_fields=["stripe_price_id"])

    subscription = SubscriptionFactory(
        plan=pro_plan,
        stripe_subscription_id="sub_123",
    )

    mock_retrieve.return_value = {"items": {"data": []}}

    with pytest.raises(APIException):
        StripeService.change_plan(subscription, business_plan)
