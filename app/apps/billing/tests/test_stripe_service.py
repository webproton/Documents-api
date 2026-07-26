# app/apps/billing/tests/test_stripe_service.py

from unittest.mock import Mock, patch

import pytest
import stripe
from django.conf import settings
from rest_framework.exceptions import APIException

from app.apps.billing.models import Order
from app.apps.billing.services import StripeService
from app.apps.billing.tests.factories.order import OrderFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Customer.create")
def test_get_or_create_customer_returns_existing_customer(
    mock_customer_create,
):
    subscription = SubscriptionFactory(stripe_customer_id="cus_existing")

    customer_id = StripeService.get_or_create_customer(subscription.user)

    assert customer_id == "cus_existing"
    mock_customer_create.assert_not_called()


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Customer.create")
def test_get_or_create_customer_creates_customer(
    mock_customer_create,
):
    subscription = SubscriptionFactory(stripe_customer_id=None)

    customer = Mock()
    customer.id = "cus_new"

    mock_customer_create.return_value = customer

    customer_id = StripeService.get_or_create_customer(subscription.user)

    subscription.refresh_from_db()

    assert customer_id == "cus_new"
    assert subscription.stripe_customer_id == "cus_new"


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.stripe.Customer.create")
def test_get_or_create_customer_handles_stripe_error(
    mock_customer_create,
):
    subscription = SubscriptionFactory(stripe_customer_id=None)

    mock_customer_create.side_effect = stripe.error.StripeError(message="Boom")

    with pytest.raises(APIException):
        StripeService.get_or_create_customer(subscription.user)


@pytest.mark.django_db
def test_create_order():
    subscription = SubscriptionFactory()

    order = StripeService.create_order(
        subscription.user,
        subscription.plan,
    )

    assert order.user == subscription.user
    assert order.plan == subscription.plan
    assert order.amount == subscription.plan.price
    assert order.currency == settings.DEFAULT_CURRENCY
    assert order.status == Order.STATUS.PENDING


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.StripeService.get_or_create_customer")
@patch("app.apps.billing.services.stripe.stripe.checkout.Session.create")
def test_create_checkout_session(
    mock_session_create,
    mock_get_customer,
):
    subscription = SubscriptionFactory()
    order = OrderFactory(
        user=subscription.user,
        subscription=subscription,
        plan=subscription.plan,
    )

    mock_get_customer.return_value = "cus_test"

    session = Mock()
    session.id = "cs_test"

    mock_session_create.return_value = session

    result = StripeService.create_checkout_session(
        subscription.user,
        subscription.plan,
        order=order,
    )

    assert result == session

    mock_session_create.assert_called_once()


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.StripeService.get_or_create_customer")
@patch("app.apps.billing.services.stripe.stripe.checkout.Session.create")
def test_create_checkout_session_handles_stripe_error(
    mock_session_create,
    mock_get_customer,
):
    subscription = SubscriptionFactory()

    order = OrderFactory(
        user=subscription.user,
        subscription=subscription,
        plan=subscription.plan,
    )

    mock_get_customer.return_value = "cus_test"

    mock_session_create.side_effect = stripe.error.StripeError(message="Boom")

    with pytest.raises(APIException):
        StripeService.create_checkout_session(
            subscription.user,
            subscription.plan,
            order=order,
        )


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.StripeService.create_checkout_session")
def test_start_checkout(
    mock_create_checkout_session,
):
    subscription = SubscriptionFactory()

    session = Mock()
    session.id = "cs_test"

    mock_create_checkout_session.return_value = session

    StripeService.start_checkout(
        subscription.user,
        subscription.plan,
    )

    order = Order.objects.get()

    assert order.stripe_checkout_session_id == "cs_test"


@pytest.mark.django_db
@patch("app.apps.billing.services.stripe.StripeService.create_checkout_session")
def test_start_checkout_deletes_order_on_error(
    mock_create_checkout_session,
):
    subscription = SubscriptionFactory()

    mock_create_checkout_session.side_effect = APIException("Stripe error")

    with pytest.raises(APIException):
        StripeService.start_checkout(
            subscription.user,
            subscription.plan,
        )

    assert Order.objects.count() == 0
