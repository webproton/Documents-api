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

    def get(self, request, format=None):
        subscription = (
            request.user.subscriptions.select_related("plan")
            .filter(status=Subscription.STATUS.ACTIVE)
            .first()
        )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
