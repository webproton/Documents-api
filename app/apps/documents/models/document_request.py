# documents/models/document_request.py
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
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

    @transaction.atomic
    def resend_notification(self):
        """
        Resends the notification email for the document request.
        Restricts resending to at most once per hour using select_for_update
        to prevent concurrent duplicate email sends.
        """
        # Acquire row lock to ensure serialized execution for this request instance
        locked_request = DocumentRequest.objects.select_for_update().get(pk=self.pk)

        # Check rate limit inside the transaction under lock
        if (
            locked_request.last_sent_at
            and timezone.now() - locked_request.last_sent_at < timedelta(hours=1)
        ):
            raise ValidationError("You can resend notification once per hour.")

        now = timezone.now()
        locked_request.last_sent_at = now
        locked_request.save(update_fields=["last_sent_at"])

        # Sync current in-memory instance
        self.last_sent_at = now

        # Import task locally to prevent circular imports
        from app.apps.notifications.tasks import send_notification_email_task

        # Trigger email send strictly after the database commit
        transaction.on_commit(
            lambda: send_notification_email_task.delay(
                recipient_email=locked_request.recipient_email,
                context=locked_request.get_email_context(),
                notification_code="DOCUMENT_REQUEST",
                title=f"Document Request: {locked_request.document_type.name}",
                user_id=locked_request.requester.id,
                document_id=locked_request.id,
            )
        )

    @transaction.atomic
    def cancel(self):
        """
        Cancels the document request if it is in PENDING status.
        Uses select_for_update to prevent race conditions
        during concurrent updates.
        """
        # Lock and retrieve the database row to prevent concurrent modification
        locked_request = DocumentRequest.objects.select_for_update().get(pk=self.pk)

        if locked_request.status != self.STATUS.PENDING:
            raise ValidationError("Cannot cancel a request that is not pending.")

        locked_request.status = self.STATUS.CANCELED
        locked_request.save(update_fields=["status"])

        # Sync current in-memory instance status
        self.status = locked_request.status
