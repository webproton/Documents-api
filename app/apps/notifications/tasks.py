import logging

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from app.apps.notifications.models import Notification

logger = logging.getLogger(__name__)


@shared_task
def send_notification_email_task(
    recipient_email, context, notification_code, title, user_id=None, document_id=None
):
    """
    task for compiling and sending emails.
    Logs the process to the Notification model.
    """
    # select template
    if notification_code == Notification.TYPE.EMAIL_CONFIRMATION:
        template_name = "notifications/email_confirmation.html"
    elif notification_code == Notification.TYPE.DOCUMENT_REQUEST:
        template_name = "notifications/document_request.html"
    else:
        template_name = "notifications/base_email.html"

    try:
        # render html content from template, context
        html_message = render_to_string(template_name, context)

        notification = Notification.objects.create(
            recipient_email=recipient_email,
            type=notification_code,
            message=html_message,
            title=title,
            user_id=user_id,
            status=Notification.STATUS.PENDING,
            document_id=document_id,
        )

        send_mail(
            subject=title,
            message="",
            from_email=None,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )

        # if success update status
        notification.status = Notification.STATUS.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at"])
    except Exception as e:
        logger.error(f"Error sending email to  {recipient_email}: {str(e)}")

        # If it crashed BEFORE creating a record in the database,
        #  we create it immediately with the FAILED status
        if "notification" not in locals():
            Notification.objects.create(
                recipient_email=recipient_email,
                type=notification_code,
                title=title,
            )
        else:
            # If there was already a recording, just switch to FAILED
            notification.status = Notification.STATUS.FAILED
            notification.save(update_fields=["status"])
