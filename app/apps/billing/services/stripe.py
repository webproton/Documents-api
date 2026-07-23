# payments/services.py
import stripe
from django.conf import settings
from rest_framework.exceptions import APIException

from app.apps.billing.models import Order, Plan

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


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
            raise APIException(exc.user_message or str(exc))

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
            raise APIException(exc.user_message or str(exc))

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

        if plan.name == Plan.NAME.FREE:
            raise APIException("FREE plan cannot be purchased.")

        if not plan.stripe_price_id:
            raise APIException("Stripe price is not configured for this plan.")

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
