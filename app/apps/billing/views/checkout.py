# app/apps/billing/views/checkout.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import CheckoutSerializer
from app.apps.billing.services import StripeService


class CheckoutView(APIView):
    """
    API endpoint for creating a Stripe Checkout session.

    Validates the selected subscription plan before
    creating a checkout session.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = CheckoutSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        session = StripeService.start_checkout(
            user=request.user,
            plan=serializer.validated_data["plan"],
        )
        return Response(
            {
                "checkout_url": session.url,
                "session_id": session.id,
            },
            status=status.HTTP_200_OK,
        )
