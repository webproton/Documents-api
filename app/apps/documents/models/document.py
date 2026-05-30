# documents/models/document.py
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


def document_upload_to(instance, filename):
    """generate a secure path for S3
    uses uuid to uniq. and protect user privacy"""
    filename = get_valid_filename(filename)
    return (
        f"documents/{instance.user_id}/{instance.document_type_id}/"
        f"{uuid.uuid4()}/{filename}"
    )


class Document(TimeStampedModel, StatusModel):
    """
    Represent a physical file uploaded by a user.
    Uses model_utils.StatusModel to manage ACTIVE/REPLACED versiong.

    """

    STATUS = Choices(
        ("ACTIVE", "Active"),
        ("REPLACED", "Replaced"),
    )

    name = models.CharField(max_length=200, verbose_name=_("Name"))

    file = models.FileField(
        upload_to=document_upload_to,
        verbose_name=_("File"),
    )

    document_type = models.ForeignKey(
        "documents.DocumentType",
        on_delete=models.PROTECT,
        verbose_name=_("Document type"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="documents",
    )

    expiration_date = models.DateField(
        verbose_name=_("Expiration date"), null=True, blank=True
    )

    class Meta:
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["user", "document_type"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")

    def __str__(self):
        return f"{self.name} ({self.document_type.name})"
