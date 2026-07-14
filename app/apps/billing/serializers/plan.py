from rest_framework import serializers

from app.apps.billing.models import Plan


class PlanSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying available subscription plans.

    Provides public information about subscription plans
    available for purchase.
    """

    class Meta:
        model = Plan
        fields = (
            "id",
            "name",
            "description",
            "document_limit",
            "price",
        )
        read_only_fields = fields
