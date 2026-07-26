# app/apps/billing/views/subscription.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.models import Subscription
from app.apps.billing.serializers import SubscriptionSerializer


class CurrentSubscriptionView(APIView):
    """
    Retrieve the authenticated user's current subscription.
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        subscription = (
            Subscription.objects.select_related("plan")
            .filter(
                user=request.user,
                status=Subscription.STATUS.ACTIVE,
            )
            .first()
        )

        if subscription is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
