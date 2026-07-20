# billing/models/plan.py


from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import TimeStampedModel


class Plan(TimeStampedModel):
    """Subscription plan defining pricing and document limits.

    FREE plan has limited documents, PRO/BUSINESS have higher or unlimited limits.
    """

    NAME = Choices(
        ("FREE", _("Free")),
        ("PRO", _("Pro")),
        ("BUSINESS", _("Business")),
    )
    name = models.CharField(
        verbose_name=_("Name"), max_length=20, choices=NAME, unique=True
    )
    document_limit = models.IntegerField(
        verbose_name=_("Document Limit"),
        null=True,
        blank=True,
        help_text=_("Null means unlimited"),
    )
    price = models.DecimalField(
        verbose_name=_("Price"), max_digits=10, decimal_places=2, default=0
    )
    stripe_price_id = models.CharField(
        verbose_name=_("Stripe Price ID"), max_length=255, blank=True, null=True
    )
    description = models.TextField(verbose_name=_("Description"), blank=True)
    is_active = models.BooleanField(verbose_name=_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")

    def __str__(self):
        return f"{self.get_name_display()}"
