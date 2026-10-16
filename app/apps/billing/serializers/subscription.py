from rest_framework import serializers

from app.apps.billing.models import Subscription
from app.apps.billing.serializers.plan import PlanSerializer
from app.apps.documents.models import Document


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the current user's subscription.

    Provides information about the active subscription,
    selected plan, billing status, and subscription period.
    """

    plan = PlanSerializer(read_only=True)
    # Same rule as CheckDocumentLimitSerializerMixin: every uploaded
    # document counts towards the plan limit, replaced ones included
    documents_used = serializers.SerializerMethodField()

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
            "documents_used",
        )
        read_only_fields = fields

    def get_documents_used(self, obj) -> int:
        return Document.objects.filter(user_id=obj.user_id).count()
