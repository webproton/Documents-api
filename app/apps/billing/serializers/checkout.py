from rest_framework import serializers

from app.apps.billing.models import Plan


class CheckoutSerializer(serializers.Serializer):
    """
    Serializer for validating checkout session requests.

    Validates that the selected subscription plan
    is available for purchase.
    """

    # return active plan
    plan = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(is_active=True)
    )

    def validate_plan(self, plan):
        """
        Validate that the selected plan can be purchased.
        """

        if plan.name == Plan.NAME.FREE:
            raise serializers.ValidationError("The FREE plan cannot be purchased.")

        if not plan.stripe_price_id:
            raise serializers.ValidationError(
                "Stripe price is not configured for this plan."
            )

        return plan


class CheckoutResponseSerializer(serializers.Serializer):
    """Response shape for a created Stripe Checkout session."""

    checkout_url = serializers.URLField()
    session_id = serializers.CharField()
