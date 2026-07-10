# billing/models/subscription.py


from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


class Subscription(TimeStampedModel, StatusModel):
    """User's active subscription to a Plan.

    Links user with current plan, tracks Stripe subscription and billing period.
    """

    STATUS = Choices(
        ("PENDING", _("Pending")),
        ("ACTIVE", _("Active")),
        ("CANCELED", _("Canceled")),
        ("EXPIRED", _("Expired")),
        ("FAILED", _("Failed")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="subscriptions",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )
    plan = models.ForeignKey(
        "billing.Plan",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Plan"),
    )
    start_date = models.DateTimeField(
        verbose_name=_("Start Date"), null=True, blank=True
    )

    end_date = models.DateTimeField(verbose_name=_("End Date"), null=True, blank=True)
    stripe_subscription_id = models.CharField(
        verbose_name=_("Stripe Subscription ID"), max_length=255, blank=True, null=True
    )
    stripe_customer_id = models.CharField(
        verbose_name=_("Stripe Customer ID"), max_length=255, blank=True, null=True
    )
    current_period_end = models.DateTimeField(
        verbose_name=_("Current Period End"), null=True, blank=True
    )
    cancel_at_period_end = models.BooleanField(
        verbose_name=_("Cancel At Period End"), default=False
    )

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"
