# documents/models/document_request.py
import uuid

from django.conf import settings
from django.db import models


class DocumentRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    COMPLETED = "COMPLETED", "Completed"
    CANCELED = "CANCELED", "Canceled"
    EXPIRED = "EXPIRED", "Expired"


class DocumentRequest(models.Model):
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_requests",
        verbose_name="Requester",
    )

    recipient_email = models.EmailField(verbose_name="Recipient email")

    document_type = models.ForeignKey(
        "documents.DocumentType",
        on_delete=models.PROTECT,
        verbose_name="Document type",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Token",
    )

    status = models.CharField(
        max_length=10,
        choices=DocumentRequestStatus.choices,
        default=DocumentRequestStatus.PENDING,
        verbose_name="Status",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")

    expires_at = models.DateTimeField(verbose_name="Expires at")

    last_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last sent at",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document request"
        verbose_name_plural = "Document requests"

    def __str__(self):
        return f"Request for {self.document_type.name} to {self.recipient_email}"
