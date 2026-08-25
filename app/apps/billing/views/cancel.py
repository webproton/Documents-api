# billing/views/cancel.py
from drf_yasg.utils import no_body, swagger_auto_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import CancelSubscriptionSerializer
from app.apps.common.serializers import MessageSerializer


class CancelSubscriptionView(APIView):
    """
    Cancel the authenticated user's subscription at the end of the
    current billing period.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Cancel subscription",
        operation_description=(
            "Cancel the authenticated user's subscription "
            "at the end of the current billing period. "
            "No request body is required."
        ),
        request_body=no_body,
        responses={
            200: MessageSerializer,
            400: "No active paid subscription to cancel.",
        },
    )
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
