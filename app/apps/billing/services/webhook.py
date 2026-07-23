# app/apps/billing/services/webhook.py

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from app.apps.billing.models import Order, StripeWebhookEvent, Subscription


class StripeWebhookService:
    """
    Service responsible for processing Stripe webhook events.
    """

    @staticmethod
    @transaction.atomic
    def process(event):
        """
        Process a Stripe webhook event.

        Prevents duplicate processing by storing Stripe event ids.
        """

        webhook_event, created = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event["id"],
            defaults={
                "event_type": event["type"],
                "raw_payload": event,
            },
        )

        if webhook_event.processed:
            return

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

        handler(event)

        webhook_event.processed = True
        webhook_event.save(update_fields=["processed", "processed_at"])

    @staticmethod
    def handle_checkout_completed(event):
        """
        Handle checkout.session.completed event.

        Links the created Stripe objects to the pending order.
        """

        session = event["data"]["object"]

        order = Order.objects.get(
            stripe_checkout_session_id=session["id"],
        )

        order.stripe_customer_id = session.get("customer")
        order.stripe_payment_intent_id = session.get("payment_intent")

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
        """

        invoice = event["data"]["object"]

        subscription = Subscription.objects.get(
            stripe_subscription_id=invoice["subscription"],
        )

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
            order.save(
                update_fields=[
                    "status",
                    "stripe_invoice_id",
                ]
            )

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
        """

        invoice = event["data"]["object"]

        subscription = Subscription.objects.get(
            stripe_subscription_id=invoice["subscription"],
        )

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
        """

        stripe_subscription = event["data"]["object"]

        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription["id"],
        )

        subscription.status = Subscription.STATUS.EXPIRED
        subscription.end_date = timezone.now()
        subscription.cancel_at_period_end = False

        subscription.save(
            update_fields=[
                "status",
                "end_date",
                "cancel_at_period_end",
            ]
        )
