# app/apps/billing/views/webhook.py

import stripe
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.services import StripeWebhookService


class StripeWebhookView(APIView):
    """
    Stripe webhook endpoint.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @swagger_auto_schema(
        operation_summary="Stripe webhook",
        operation_description=(
            "Receive and verify Stripe webhook events. "
            "Authentication is performed using the Stripe-Signature header."
        ),
        manual_parameters=[
            openapi.Parameter(
                "Stripe-Signature",
                openapi.IN_HEADER,
                description="Stripe webhook signature.",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: "Webhook processed successfully.",
            400: "Missing or invalid Stripe signature or payload.",
        },
    )
    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get("Stripe-Signature")

        if not signature:
            return Response(
                {"detail": "Missing Stripe-Signature header."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.SignatureVerificationError:
            return Response(
                {"detail": "Invalid Stripe signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        StripeWebhookService.process(event)

        return Response(status=status.HTTP_200_OK)
