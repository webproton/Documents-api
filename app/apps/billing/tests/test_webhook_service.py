import pytest
from django.utils import timezone

from app.apps.billing.models import Order, StripeWebhookEvent, Subscription
from app.apps.billing.services import StripeWebhookService
from app.apps.billing.tests.factories.order import OrderFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


def checkout_completed_event(
    *,
    event_id="evt_checkout",
    session_id="cs_test",
    customer="cus_test",
    payment_intent="pi_test",
    subscription="sub_test",
):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "customer": customer,
                "payment_intent": payment_intent,
                "subscription": subscription,
            }
        },
    }


def invoice_paid_event(
    *,
    event_id="evt_paid",
    subscription="sub_test",
    customer="cus_test",
    invoice="in_test",
):
    return {
        "id": event_id,
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": subscription,
                "customer": customer,
                "id": invoice,
                "period_end": int(timezone.now().timestamp()) + 3600,
            }
        },
    }


def invoice_failed_event(
    *,
    event_id="evt_failed",
    subscription="sub_test",
    invoice="in_failed",
):
    return {
        "id": event_id,
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": subscription,
                "id": invoice,
            }
        },
    }


def subscription_deleted_event(
    *,
    event_id="evt_deleted",
    subscription="sub_test",
):
    return {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": subscription,
            }
        },
    }


@pytest.mark.django_db
def test_checkout_completed_updates_order():
    order = OrderFactory(
        stripe_checkout_session_id="cs_test",
    )

    StripeWebhookService.process(checkout_completed_event())

    order.refresh_from_db()

    assert order.stripe_customer_id == "cus_test"
    assert order.stripe_payment_intent_id == "pi_test"
    assert StripeWebhookEvent.objects.count() == 1


@pytest.mark.django_db
def test_invoice_paid_updates_subscription_and_order():
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.PENDING,
    )

    order = OrderFactory(
        subscription=subscription,
        status=Order.STATUS.PENDING,
    )

    StripeWebhookService.process(invoice_paid_event())

    subscription.refresh_from_db()
    order.refresh_from_db()

    assert subscription.status == Subscription.STATUS.ACTIVE
    assert subscription.stripe_customer_id == "cus_test"
    assert subscription.current_period_end is not None
    assert subscription.cancel_at_period_end is False

    assert order.status == Order.STATUS.PAID
    assert order.stripe_invoice_id == "in_test"


@pytest.mark.django_db
def test_invoice_failed_updates_subscription_and_order():
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.ACTIVE,
    )

    order = OrderFactory(
        subscription=subscription,
        status=Order.STATUS.PENDING,
    )

    StripeWebhookService.process(invoice_failed_event())

    subscription.refresh_from_db()
    order.refresh_from_db()

    assert subscription.status == Subscription.STATUS.FAILED
    assert order.status == Order.STATUS.FAILED
    assert order.stripe_invoice_id == "in_failed"


@pytest.mark.django_db
def test_subscription_deleted_expires_subscription():
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
    )

    StripeWebhookService.process(subscription_deleted_event())

    subscription.refresh_from_db()

    assert subscription.status == Subscription.STATUS.EXPIRED
    assert subscription.end_date is not None
    assert subscription.cancel_at_period_end is False


@pytest.mark.django_db
def test_duplicate_event_is_processed_once():
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.ACTIVE,
    )

    order = OrderFactory(
        subscription=subscription,
        status=Order.STATUS.PENDING,
    )

    event = invoice_failed_event(event_id="evt_duplicate")

    StripeWebhookService.process(event)
    StripeWebhookService.process(event)

    subscription.refresh_from_db()
    order.refresh_from_db()

    assert StripeWebhookEvent.objects.count() == 1
    assert order.status == Order.STATUS.FAILED
    assert subscription.status == Subscription.STATUS.FAILED
