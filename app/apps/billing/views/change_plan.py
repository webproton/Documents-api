# billing/views/change_plan.py
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import CheckoutSerializer, SubscriptionSerializer
from app.apps.billing.services import StripeService


class ChangePlanView(APIView):
    """
    Create a Stripe Checkout Session for changing
    the current subscription plan.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        subscription = request.user.subscription
        plan = serializer.validated_data["plan"]

        if subscription.plan_id == plan.id:
            raise serializers.ValidationError(
                {"plan": ["You are already subscribed to this plan."]}
            )

        if not subscription.stripe_subscription_id:
            # The first payment has not yet been made
            # – not a change of plan, but a regular checkout
            session = StripeService.start_checkout(user=request.user, plan=plan)
            return Response({"checkout_url": session.url, "session_id": session.id})

        subscription = StripeService.change_plan(subscription, plan)
        return Response(SubscriptionSerializer(subscription).data)
