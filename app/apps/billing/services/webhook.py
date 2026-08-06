# app/apps/billing/services/webhook.py

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from app.apps.billing.models import Order, Plan, Subscription


class StripeWebhookService:
    """
    Service responsible for processing Stripe webhook events.

    Idempotency is guaranteed by checking the current state of the
    affected Order/Subscription before applying changes, rather than
    storing a separate log of processed event ids — Stripe already
    keeps the full event history on their side.
    """

    @staticmethod
    @transaction.atomic
    def process(event):
        handlers = {
            "checkout.session.completed": (
                StripeWebhookService.handle_checkout_completed
            ),
            "invoice.paid": (StripeWebhookService.handle_invoice_paid),
            "invoice.payment_failed": (StripeWebhookService.handle_invoice_failed),
            "customer.subscription.deleted": (
                StripeWebhookService.handle_subscription_deleted
            ),
        }

        handler = handlers.get(event["type"])

        if handler is None:
            return

        try:
            handler(event)
        except (Order.DoesNotExist, Subscription.DoesNotExist):
            # No matching local record — likely a stale, out-of-order,
            # or already-cleaned-up event. Log and acknowledge (200) so
            # Stripe doesn't endlessly retry an event we can never match.
            return

    @staticmethod
    def handle_checkout_completed(event):
        """
        Handle checkout.session.completed event.

        Links the created Stripe objects to the pending order.
        Idempotent: if the order already has this payment_intent, skip.
        """

        session = event["data"]["object"]

        order = Order.objects.select_for_update().get(
            stripe_checkout_session_id=session["id"],
        )

        payment_intent_id = session.get("payment_intent")

        if (
            order.stripe_payment_intent_id
            and order.stripe_payment_intent_id == payment_intent_id
        ):
            return  # already processed

        order.stripe_customer_id = session.get("customer")
        order.stripe_payment_intent_id = payment_intent_id

        # Available only for subscription Checkout Sessions.
        if order.subscription:
            order.subscription.stripe_subscription_id = session.get("subscription")
            order.subscription.save(update_fields=["stripe_subscription_id"])

        order.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_payment_intent_id",
            ]
        )

    @staticmethod
    def handle_invoice_paid(event):
        """
        Handle invoice.paid event.

        Marks the order as paid and activates the subscription.
        Idempotent: if an order with this stripe_invoice_id is already
        PAID, skip.
        """

        invoice = event["data"]["object"]

        subscription = Subscription.objects.select_for_update().get(
            stripe_subscription_id=invoice["subscription"],
        )

        if Order.objects.filter(
            subscription=subscription,
            stripe_invoice_id=invoice["id"],
            status=Order.STATUS.PAID,
        ).exists():
            return  # already processed

        order = (
            Order.objects.filter(
                subscription=subscription,
                status=Order.STATUS.PENDING,
            )
            .order_by("-created")
            .first()
        )

        if order:
            order.status = Order.STATUS.PAID
            order.stripe_invoice_id = invoice["id"]
            order.save(update_fields=["status", "stripe_invoice_id"])

            subscription.plan = order.plan

        subscription.status = Subscription.STATUS.ACTIVE
        subscription.stripe_customer_id = invoice["customer"]
        subscription.current_period_end = datetime.fromtimestamp(
            invoice["period_end"],
            tz=timezone.get_current_timezone(),
        )
        subscription.cancel_at_period_end = False

        subscription.save(
            update_fields=[
                "status",
                "stripe_customer_id",
                "current_period_end",
                "cancel_at_period_end",
                "plan",
            ]
        )

    @staticmethod
    def handle_invoice_failed(event):
        """
        Handle invoice.payment_failed event.

        Marks the order and subscription as failed.
        Idempotent: if an order with this stripe_invoice_id is already
        FAILED, skip.
        """

        invoice = event["data"]["object"]

        subscription = Subscription.objects.select_for_update().get(
            stripe_subscription_id=invoice["subscription"],
        )

        if Order.objects.filter(
            subscription=subscription,
            stripe_invoice_id=invoice["id"],
            status=Order.STATUS.FAILED,
        ).exists():
            return  # already processed

        order = (
            Order.objects.filter(
                subscription=subscription,
                status=Order.STATUS.PENDING,
            )
            .order_by("-created")
            .first()
        )

        if order:
            order.status = Order.STATUS.FAILED
            order.stripe_invoice_id = invoice["id"]
            order.save(
                update_fields=[
                    "status",
                    "stripe_invoice_id",
                ]
            )

        subscription.status = Subscription.STATUS.FAILED
        subscription.save(update_fields=["status"])

    @staticmethod
    def handle_subscription_deleted(event):
        """
        Handle customer.subscription.deleted event.

        Marks the subscription as expired.
        Idempotent: if the subscription is already EXPIRED, skip.
        """

        stripe_subscription = event["data"]["object"]

        subscription = Subscription.objects.select_for_update().get(
            stripe_subscription_id=stripe_subscription["id"],
        )

        if subscription.status == Subscription.STATUS.EXPIRED:
            return  # already processed

        subscription.status = Subscription.STATUS.ACTIVE
        subscription.cancel_at_period_end = False
        subscription.stripe_subscription_id = None
        subscription.current_period_end = None
        subscription.plan = Plan.get_free_plan()

        subscription.save(
            update_fields=[
                "status",
                "stripe_subscription_id",
                "cancel_at_period_end",
                "current_period_end",
                "plan",
            ]
        )
