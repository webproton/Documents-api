# billing/views/cancel.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.models import Subscription
from app.apps.billing.services import StripeService


class CancelSubscriptionView(APIView):
    """
    Cancel the authenticated user's subscription
    at the end of the current billing period.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(user=request.user).first()

        if (
            subscription is None
            or subscription.status != Subscription.STATUS.ACTIVE
            or not subscription.stripe_subscription_id
        ):
            return Response(
                {"detail": "No active paid subscription to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StripeService.cancel_subscription(subscription)

        return Response(
            {
                "message": (
                    "Subscription will be canceled at the end "
                    "of the current billing period"
                ),
            },
            status=status.HTTP_200_OK,
        )
