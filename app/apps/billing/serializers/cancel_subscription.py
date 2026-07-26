# app/apps/billing/serializers/cancel_subscription.py

from rest_framework import serializers

from app.apps.billing.models import Subscription
from app.apps.billing.services import StripeService


class CancelSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for canceling the authenticated user's subscription
    at the end of the current billing period.
    """

    def validate(self, attrs):
        subscription = Subscription.objects.filter(
            user=self.context["request"].user
        ).first()

        if (
            subscription is None
            or subscription.status != Subscription.STATUS.ACTIVE
            or not subscription.stripe_subscription_id
        ):
            raise serializers.ValidationError("No active paid subscription to cancel.")

        attrs["subscription"] = subscription
        return attrs

    def save(self, **kwargs):
        subscription = self.validated_data["subscription"]
        return StripeService.cancel_subscription(subscription)
