# app/apps/billing/views/checkout.py
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.accounts.permissions import IsActiveAndNotBlocked
from app.apps.billing.serializers import CheckoutResponseSerializer, CheckoutSerializer
from app.apps.billing.services import StripeService


class CheckoutView(APIView):
    """
    API endpoint for creating a Stripe Checkout session.

    Validates the selected subscription plan before
    creating a checkout session.
    """

    permission_classes = (IsActiveAndNotBlocked,)

    @swagger_auto_schema(
        operation_summary="Create Stripe Checkout session",
        operation_description=(
            "Validate the selected subscription plan and create "
            "a Stripe Checkout session."
        ),
        request_body=CheckoutSerializer,
        responses={
            200: CheckoutResponseSerializer,
            400: "Invalid or unavailable subscription plan.",
        },
    )
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
