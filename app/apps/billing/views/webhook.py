# app/apps/billing/views/webhook.py

import stripe
from django.conf import settings
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
