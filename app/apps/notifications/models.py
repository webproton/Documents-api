from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from model_utils.models import StatusModel, TimeStampedModel


class Notification(StatusModel, TimeStampedModel):
    """
    A model for tracking and logging system and email notifications.
    TimeStampedModel automatically adds the following fields:
    - `created` (replaces `created_at`)
    - `modified` (replaces `updated_at`)
    """

    STATUS = Choices(
        ("PENDING", _("Pending")),
        ("SENT", _("Sent")),
        ("FAILED", _("Failed")),
    )

    TYPE = Choices(
        ("EMAIL_CONFIRMATION", _("Email Confirmation")),
        ("DOCUMENT_REQUEST", _("Document Request")),
        ("REMINDER", _("Reminder")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
        help_text=_(
            "The user inside the system. Can be null for external document requests."
        ),
    )

    recipient_email = models.EmailField(_("Recipient Email"))

    type = models.CharField(
        max_length=30, choices=TYPE, default=TYPE.EMAIL_CONFIRMATION
    )

    # content
    title = models.CharField(max_length=255)
    message = models.TextField()

    # The exact timestamp for sending the email (filled in the Celery task upon success)
    sent_at = models.DateTimeField(null=True, blank=True)

    # checking for duplicate reminders
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created"]

    def __str__(self):
        return f"{self.recipient_email} | {self.type} | {self.status}"
