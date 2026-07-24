# app/apps/billing/tests/test_webhook_service.py
import pytest
from django.utils import timezone

from app.apps.billing.models import Order, Subscription
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


@pytest.mark.django_db
def test_checkout_completed_is_idempotent():
    """Повторная обработка того же checkout-события не должна падать
    и не должна повторно перезаписывать subscription."""
    subscription = SubscriptionFactory(stripe_subscription_id=None)
    order = OrderFactory(
        subscription=subscription,
        stripe_checkout_session_id="cs_test",
    )

    event = checkout_completed_event()

    StripeWebhookService.process(event)
    StripeWebhookService.process(event)  # дубль

    order.refresh_from_db()
    subscription.refresh_from_db()

    assert order.stripe_payment_intent_id == "pi_test"
    assert subscription.stripe_subscription_id == "sub_test"


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
def test_invoice_paid_is_idempotent():
    """Повторный invoice.paid не должен пытаться искать
    второй несуществующий PENDING Order и падать."""
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.PENDING,
    )
    order = OrderFactory(
        subscription=subscription,
        status=Order.STATUS.PENDING,
    )

    event = invoice_paid_event()

    StripeWebhookService.process(event)
    StripeWebhookService.process(event)  # дубль — не должен падать

    order.refresh_from_db()
    subscription.refresh_from_db()

    assert order.status == Order.STATUS.PAID
    assert subscription.status == Subscription.STATUS.ACTIVE


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
def test_duplicate_subscription_deleted_event_is_processed_once():
    """Повторный subscription.deleted не должен перезаписывать end_date."""
    subscription = SubscriptionFactory(
        stripe_subscription_id="sub_test",
        status=Subscription.STATUS.ACTIVE,
    )

    event = subscription_deleted_event(event_id="evt_duplicate")

    StripeWebhookService.process(event)
    subscription.refresh_from_db()
    first_end_date = subscription.end_date

    StripeWebhookService.process(event)  # дубль, statys уже EXPIRED
    subscription.refresh_from_db()

    assert subscription.status == Subscription.STATUS.EXPIRED
    assert subscription.end_date == first_end_date  # не перезаписан повторно


@pytest.mark.django_db
def test_duplicate_invoice_failed_event_is_processed_once():
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
    StripeWebhookService.process(event)  # дубль

    subscription.refresh_from_db()
    order.refresh_from_db()

    assert order.status == Order.STATUS.FAILED
    assert subscription.status == Subscription.STATUS.FAILED
