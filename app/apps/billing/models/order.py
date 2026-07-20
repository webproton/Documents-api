# billing/models/order.py

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


class Order(TimeStampedModel, StatusModel):
    """Payment order for a subscription plan.

    Created when user starts checkout. Tracks the entire payment lifecycle.
    """

    STATUS = Choices(
        ("PENDING", _("Pending")),
        ("PAID", _("Paid")),
        ("FAILED", _("Failed")),
        ("REFUNDED", _("Refunded")),
        ("PARTIALLY_REFUNDED", _("Partial Refunded")),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name=_("User"),
    )
    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name=_("Subscription"),
    )
    plan = models.ForeignKey(
        "billing.Plan",
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
        verbose_name=_("Plan"),
    )
    amount = models.DecimalField(
        verbose_name=_("Amount"), max_digits=10, decimal_places=2
    )
    currency = models.CharField(
        verbose_name=_("Currency"), max_length=3, default=settings.DEFAULT_CURRENCY
    )
    stripe_payment_intent_id = models.CharField(
        verbose_name=_("Stripe Payment Intent ID"),
        max_length=255,
        blank=True,
        null=True,
    )
    stripe_invoice_id = models.CharField(
        verbose_name=_("Stripe Invoice ID"), max_length=255, blank=True, null=True
    )
    stripe_checkout_session_id = models.CharField(
        verbose_name=_("Stripe Checkout Session ID"),
        max_length=255,
        blank=True,
        null=True,
    )
    stripe_customer_id = models.CharField(
        verbose_name=_("Stripe Customer ID"), max_length=255, blank=True, null=True
    )
    metadata = models.JSONField(verbose_name=_("Metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        return f"Order {self.id} - {self.status}"
