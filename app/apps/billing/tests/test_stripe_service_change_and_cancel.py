# app/apps/billing/tests/test_stripe_service_change_and_cancel.py
from unittest.mock import patch

import pytest
import stripe
from rest_framework.exceptions import APIException

from app.apps.billing.models import Plan
from app.apps.billing.services.stripe import StripeService
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


@pytest.mark.django_db
def test_change_plan_no_stripe_subscription_raises():
    subscription = SubscriptionFactory(stripe_subscription_id=None)
    new_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")

    with pytest.raises(APIException):
        StripeService.change_plan(subscription, new_plan)


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.modify")
@patch("app.apps.billing.services.stripe.stripe.Subscription.retrieve")
def test_change_plan_updates_local_plan(mock_retrieve, mock_modify):
    old_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")
    new_plan = PlanFactory(name=Plan.NAME.BUSINESS, stripe_price_id="price_business")
    subscription = SubscriptionFactory(
        plan=old_plan,
        stripe_subscription_id="sub_123",
    )
    mock_retrieve.return_value = {"items": {"data": [{"id": "si_1"}]}}

    result = StripeService.change_plan(subscription, new_plan)

    assert result.plan == new_plan
    mock_modify.assert_called_once_with(
        "sub_123",
        items=[{"id": "si_1", "price": "price_business"}],
        proration_behavior="create_prorations",
    )


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.retrieve")
def test_change_plan_stripe_error_raises_api_exception(mock_retrieve):
    subscription = SubscriptionFactory(stripe_subscription_id="sub_123")
    new_plan = PlanFactory(name=Plan.NAME.PRO, stripe_price_id="price_pro")

    mock_retrieve.side_effect = stripe.error.StripeError("boom")

    with pytest.raises(APIException):
        StripeService.change_plan(subscription, new_plan)


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.modify")
def test_cancel_subscription_sets_cancel_at_period_end(mock_modify):
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_123",
        cancel_at_period_end=False,
    )

    result = StripeService.cancel_subscription(subscription)

    assert result.cancel_at_period_end is True
    mock_modify.assert_called_once_with("sub_123", cancel_at_period_end=True)


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Subscription.modify")
def test_cancel_subscription_stripe_error_raises_api_exception(mock_modify):
    subscription = SubscriptionFactory(stripe_subscription_id="sub_123")
    mock_modify.side_effect = stripe.error.StripeError("boom")

    with pytest.raises(APIException):
        StripeService.cancel_subscription(subscription)
