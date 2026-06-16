# documents/models/document_request.py
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


class DocumentRequest(TimeStampedModel, StatusModel):
    """
    Tracks secure upload requests sent to external parties.
    Allows anonymous users to upload a specific document type via a unique secure token.
    """

    STATUS = Choices(
        ("PENDING", _("Pending")),
        ("COMPLETED", _("Completed")),
        ("CANCELED", _("Canceled")),
        ("EXPIRED", _("Expired")),
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_requests",
        verbose_name=_("Requester"),
    )

    recipient_email = models.EmailField(
        verbose_name=_("Recipient email"),
    )

    document_type = models.ForeignKey(
        "documents.DocumentType",
        on_delete=models.CASCADE,
        related_name="document_requests",
        verbose_name=_("Document type"),
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("Token"),
    )

    expires_at = models.DateTimeField(
        verbose_name=_("Expires at"), null=True, blank=True
    )

    last_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last sent at"),
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = _("Document request")
        verbose_name_plural = _("Document requests")

    def __str__(self):
        return f"Request for {self.document_type.name} to {self.recipient_email}"

    def get_email_context(self) -> dict:
        """Generates a link and context for sending an email"""
        relative_url = reverse(
            "apps.documents:anonymous-upload", kwargs={"token": self.token}
        )
        base_url = settings.BACKEND_URL.rstrip("/")

        return {
            "username": self.recipient_email,
            "requester_email": self.requester.email,
            "document_type_name": self.document_type.name,
            "upload_url": f"{base_url}{relative_url}",
        }
