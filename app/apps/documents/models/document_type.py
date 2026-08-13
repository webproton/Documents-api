# documents/models/document_type.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel


class DocumentType(TimeStampedModel):
    """
    Defines document categories used for grouping user documents.

    Example: Passport, Invoice, Contract.

    Acts as a logical 'folder' to group individual user documents.
    """

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
    )

    template = models.FileField(
        upload_to="document_templates/",
        null=True,
        blank=True,
        verbose_name=_("Template"),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Document type")
        verbose_name_plural = _("Document types")

    def __str__(self) -> str:
        return self.name
