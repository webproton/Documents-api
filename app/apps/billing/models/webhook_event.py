# app/apps/billing/models/webhook_event.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel


class StripeWebhookEvent(TimeStampedModel):
    """
    Stores received Stripe webhook events.

    Used for idempotent webhook processing.
    """

    stripe_event_id = models.CharField(
        verbose_name=_("Stripe Event ID"),
        max_length=255,
        unique=True,
    )

    raw_payload = models.JSONField(
        verbose_name=_("Raw Payload"),
    )

    processed = models.BooleanField(
        default=False,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    event_type = models.CharField(
        max_length=100,
    )

    class Meta:
        verbose_name = _("Stripe Webhook Event")
        verbose_name_plural = _("Stripe Webhook Events")

    def __str__(self):
        return self.stripe_event_id
