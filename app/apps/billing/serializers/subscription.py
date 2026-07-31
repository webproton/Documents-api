from rest_framework import serializers

from app.apps.billing.models import Subscription
from app.apps.billing.serializers.plan import PlanSerializer


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the current user's subscription.

    Provides information about the active subscription,
    selected plan, billing status, and subscription period.
    """

    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "plan",
            "status",
            "start_date",
            "end_date",
            "current_period_end",
            "cancel_at_period_end",
            "created",
        )
        read_only_fields = fields
