# payments/services.py
import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

from app.apps.billing.models import Order

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeServiceError(APIException):
    """
    Raised when a call to the Stripe API fails.

    This is an upstream service failure, not a bug in our backend —
    hence 502, not the default 500 from a bare APIException.
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = (
        "Payment provider is temporarily unavailable. Please try again later."
    )
    default_code = "stripe_unavailable"


class StripeService:

    @staticmethod
    def get_or_create_customer(user):
        """
        Get an existing Stripe customer or create a new one.
        """

        subscription = user.subscription

        if subscription.stripe_customer_id:
            return subscription.stripe_customer_id
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    "user_id": str(user.id),
                },
            )
        except stripe.error.StripeError as exc:
            raise StripeServiceError(exc.user_message or str(exc))

        subscription.stripe_customer_id = customer.id
        subscription.save(update_fields=["stripe_customer_id"])

        return customer.id

    @staticmethod
    def create_checkout_session(user, plan, order):
        """
        Create a Stripe Checkout Session for a subscription plan.
        """

        customer_id = StripeService.get_or_create_customer(user)

        try:
            return stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                mode="subscription",
                line_items=[
                    {
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    }
                ],
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
                client_reference_id=str(user.id),
                metadata={
                    "user_id": str(user.id),
                    "plan_id": str(plan.id),
                },
                idempotency_key=f"checkout-{order.id}",
            )
        except stripe.error.StripeError as exc:
            raise StripeServiceError(exc.user_message or str(exc))

    @staticmethod
    def create_order(user, plan):
        """
        Create a pending order before redirecting the user to Stripe Checkout.

        Required by the billing workflow to track the payment lifecycle.
        """

        return Order.objects.create(
            user=user,
            subscription=user.subscription,
            plan=plan,
            amount=plan.price,
            currency=settings.DEFAULT_CURRENCY,
            status=Order.STATUS.PENDING,
            metadata={},
        )

    @staticmethod
    def start_checkout(user, plan):
        """
        Create a pending order and a Stripe Checkout Session.

        Links the created Checkout Session to the order.
        """

        # close hanging PENDING orders instead of accumulating duplicates
        Order.objects.filter(user=user, status=Order.STATUS.PENDING).delete()

        order = StripeService.create_order(user, plan)

        try:
            session = StripeService.create_checkout_session(user, plan, order)
        except APIException:
            order.delete()
            raise

        order.stripe_checkout_session_id = session.id
        order.save(update_fields=["stripe_checkout_session_id"])

        return session

    @staticmethod
    def change_plan(subscription, new_plan):

        try:
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            items = stripe_sub["items"]["data"]

            if not items:
                raise StripeServiceError("Stripe subscription has no items.")

            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{"id": items[0]["id"], "price": new_plan.stripe_price_id}],
                proration_behavior="create_prorations",
            )
        except stripe.error.StripeError as exc:
            raise StripeServiceError(exc.user_message or str(exc))

        subscription.plan = new_plan
        subscription.save(update_fields=["plan"])
        return subscription

    @staticmethod
    def cancel_subscription(subscription):
        """
        Cancel a subscription at the end of the current billing period.
        """

        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.error.StripeError as exc:
            raise StripeServiceError(exc.user_message or str(exc))

        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end"])

        return subscription
