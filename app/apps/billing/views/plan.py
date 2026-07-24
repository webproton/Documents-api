# app/apps/billing/views/plan.py
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

from app.apps.billing.models import Plan
from app.apps.billing.serializers import PlanSerializer


class PlanViewSet(ReadOnlyModelViewSet):
    """
    Read-only ViewSet for available subscription plans.

    Returns active plans that users can purchase.
    """

    serializer_class = PlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Plan.objects.filter(is_active=True).order_by("price")
