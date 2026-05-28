# app/apps/documents/tasks.py

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from app.apps.documents.models import DocumentRequest


@shared_task
def send_document_request_email_task(request_id: int):
    """
    Background Celery task to send a secure upload link to the recipient.
    """
    try:
        # 1. Fetch the request inside the worker process
        doc_request = DocumentRequest.objects.select_related(
            "requester", "document_type"
        ).get(id=request_id)

        # 2. Dynamically collecting the anonymous download endpoint URL
        relative_url = reverse(
            "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
        )

        # We take the base URL from the settings
        base_url = getattr(settings, "BACKEND_URL", "http://localhost:8000").rstrip("/")
        upload_url = f"{base_url}{relative_url}"

        # 3. Construct the email
        subject = f"Document Request: {doc_request.document_type.name}"
        message = (
            f"Hello!\n\n"
            f"User {doc_request.requester.email} is requesting a "
            f"{doc_request.document_type.name}.\n"
            f"Please upload the required file using this secure 30-day link:\n"
            f"{upload_url}\n"
        )

        # 4. Send via Django core mail
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[doc_request.recipient_email],
            fail_silently=False,
        )

    except DocumentRequest.DoesNotExist:
        # Safe log fallback if the request was deleted before the task started
        pass


@shared_task
def auto_expire_document_requests_task():
    """
    A periodic task to automatically convert obsolete queries to EXPIRED.
    """
    # We import inside the task to avoid circular imports
    from app.apps.documents.services.document_services import DocumentService

    expired_count = DocumentService.expire_prolonged_requests()
    return f"Successfully expired {expired_count} document requests."
