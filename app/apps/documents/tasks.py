# app/apps/documents/tasks.py

from celery import shared_task
from django.utils import timezone

from app.apps.documents.models import DocumentRequest


@shared_task
def auto_expire_document_requests_task():
    """
    A periodic task to automatically convert obsolete queries to EXPIRED.
    """
    # We import inside the task to avoid circular imports
    expired_count = DocumentRequest.objects.filter(
        status=DocumentRequest.STATUS.PENDING, expires_at__lt=timezone.now()
    ).update(status=DocumentRequest.STATUS.EXPIRED)
    return f"Successfully expired {expired_count} document requests."
