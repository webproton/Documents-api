# billing/views/cancel.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import CancelSubscriptionSerializer


class CancelSubscriptionView(APIView):
    """
    Cancel the authenticated user's subscription at the end of the
    current billing period.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = CancelSubscriptionSerializer(data={}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": (
                    "Subscription will be canceled at the end "
                    "of the current billing period"
                ),
            }
        )
