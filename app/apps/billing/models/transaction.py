# billing/models/transaction.py


from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


class Transaction(TimeStampedModel, StatusModel):
    """Financial transaction record for audit and reconciliation.

    Stores every Stripe webhook event related to payments and refunds.
    """

    STATUS = Choices(
        ("SUCCESS", _("Success")),
        ("FAILED", _("Failed")),
    )
    TYPE = Choices(
        ("PAYMENT", _("Payment")),
        ("REFUND", _("Refund")),
        ("CHARGE", "Charge"),
        ("EVENT", _("Event")),
    )
    order = models.ForeignKey(
        "billing.Order",
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
        verbose_name=_("Order"),
    )
    type = models.CharField(verbose_name=_("Type"), max_length=20, choices=TYPE)
    amount = models.DecimalField(
        verbose_name=_("Amount"), max_digits=10, decimal_places=2, blank=True, null=True
    )
    currency = models.CharField(
        verbose_name=_("Currency"), max_length=3, default=settings.DEFAULT_CURRENCY
    )
    stripe_event_id = models.CharField(
        verbose_name=_("Stripe Event ID"), max_length=255, unique=True
    )
    event_type = models.CharField(verbose_name=_("Event Type"), max_length=255)
    raw_payload = models.JSONField(
        verbose_name=_("Raw Payload"), default=dict, blank=True
    )

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")

        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["created"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(
                _("Immutable object: Transactions cannot be modified.")
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Tx {self.stripe_event_id} ({self.type})"
