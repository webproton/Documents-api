# app/apps/billing/serializers/change_plan.py

from rest_framework import serializers

from app.apps.billing.models import Plan
from app.apps.billing.serializers.subscription import SubscriptionSerializer
from app.apps.billing.services import StripeService


class ChangePlanSerializer(serializers.Serializer):
    """
    Serializer for changing the authenticated user's subscription plan.

    If the user has no active Stripe subscription yet, this falls back
    to a regular checkout (first payment). Otherwise the existing
    Stripe subscription is updated via Subscription.modify().
    """

    plan = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(is_active=True)
    )

    def validate_plan(self, plan):
        if plan.name == Plan.NAME.FREE:
            raise serializers.ValidationError("The FREE plan cannot be purchased.")
        return plan

    def validate(self, attrs):
        subscription = self.context["request"].user.subscription
        plan = attrs["plan"]

        if subscription.plan_id == plan.id:
            raise serializers.ValidationError(
                {"plan": ["You are already subscribed to this plan."]}
            )

        attrs["subscription"] = subscription
        return attrs

    def save(self, **kwargs):
        subscription = self.validated_data["subscription"]
        plan = self.validated_data["plan"]

        if not subscription.stripe_subscription_id:
            # First payment — not a plan change, a regular checkout
            session = StripeService.start_checkout(
                user=self.context["request"].user, plan=plan
            )
            return {"checkout_url": session.url, "session_id": session.id}

        updated_subscription = StripeService.change_plan(subscription, plan)
        return SubscriptionSerializer(updated_subscription).data
