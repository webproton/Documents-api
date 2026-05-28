# apps/documents/services/document_services.py
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from app.apps.documents.models import Document, DocumentRequest
from app.apps.documents.tasks import send_document_request_email_task


class DocumentService:
    """
    Encapsulates business logic operations for User Documents.
    Handles versioning, status updates, and atomicity guarantees.
    """

    @staticmethod
    def handle_anonymous_upload(
        *, token: str, file, name: str = None, expiration_date=None
    ) -> Document:
        """
        Validates the incoming token, checks expiration date, and assigns
        the uploaded document to the original requester and requested document type.
        """
        # Fetch the request by token or throw 400 validation error
        try:
            doc_request = DocumentRequest.objects.select_related(
                "document_type", "requester"
            ).get(token=token)
        except (DocumentRequest.DoesNotExist, ValueError):
            raise ValidationError({"token": "Invalid or non-existent secure token."})

        # Check if the 30-day link has already expired
        if doc_request.expires_at < timezone.now():
            raise ValidationError({"token": "This secure upload link has expired."})
        # Check status requests (should be PENDING only)
        if doc_request.status != "PENDING":
            raise ValidationError(
                {"token": f"This request is already {doc_request.status.lower()}."}
            )

        # Fallback to the uploaded file name if no explicit name was provided
        if not name:
            name = file.name

        with transaction.atomic():
            # lock the query string for updating
            doc_request = DocumentRequest.objects.select_for_update().get(
                id=doc_request.id
            )

            # Standard versioning: update previous
            # documents of the requester to REPLACED
            Document.objects.select_for_update().filter(
                user=doc_request.requester,
                document_type=doc_request.document_type,
                status="ACTIVE",
            ).update(status="REPLACED")

            # Create the incoming document linked to the request owner
            new_document = Document.objects.create(
                user=doc_request.requester,
                name=name,
                file=file,
                document_type=doc_request.document_type,
                expiration_date=expiration_date,
                status="ACTIVE",
            )

            # Change  the request status  to COMPLETED
            doc_request.status = "COMPLETED"
            doc_request.save(update_fields=["status"])

            return new_document

    @staticmethod
    def create_document(
        *, user, name: str, file, document_type, expiration_date=None
    ) -> Document:
        """
        Creates a new document and implements the versioning system:
        - Automatically marks the new document as ACTIVE.
        - Finds the previous ACTIVE document
            of the same type for this user and marks it as REPLACED.
        - Wrapped in a database transaction with row locking to prevent race conditions.
        """
        with transaction.atomic():
            # Step 1: Lock and update previous active documents
            # of the same type for this user
            # select_for_update() blocks concurrent API updates on these specific rows
            previous_active_documents = Document.objects.select_for_update().filter(
                user=user, document_type=document_type, status="ACTIVE"
            )
            previous_active_documents.update(status="REPLACED")

            # Step 2: Create the new document instance as ACTIVE
            new_document = Document.objects.create(
                user=user,
                name=name,
                file=file,
                document_type=document_type,
                expiration_date=expiration_date,
                status="ACTIVE",  # Explicitly enforce active status
            )

            return new_document

    @staticmethod
    def create_document_request(
        *, user, recipient_email: str, document_type
    ) -> DocumentRequest:
        """
        Creates a new secure document upload token for an external recipient.
        Sets a hardcoded expiration time window of 30 days.
        """
        # Calculate 30-day expiration window from current system time
        expiration_deadline = timezone.now() + timedelta(days=30)

        # Unique token field is generated automatically by the model constraint
        doc_request = DocumentRequest.objects.create(
            requester=user,
            recipient_email=recipient_email,
            document_type=document_type,
            expires_at=expiration_deadline,
        )
        # trigger Celery
        send_document_request_email_task.delay(doc_request.id)

        return doc_request

    @staticmethod
    def cancel_document_request(*, doc_request: DocumentRequest) -> DocumentRequest:
        """
        Cancels a document request, setting its status to CANCELLED.
        Prevents cancellation if the request has already been fulfilled or has expired.
        """
        if doc_request.status != "PENDING":
            raise ValidationError(
                {"detail": f"Cannot cancel a request with status {doc_request.status}."}
            )

        doc_request.status = "CANCELED"
        doc_request.save(update_fields=["status"])
        return doc_request

    @staticmethod
    def resend_document_request(*, doc_request: DocumentRequest) -> DocumentRequest:
        """
        Resends the notification if 1 hour has passed since the last sending.
        """
        # Checking if the request is in an active state
        if doc_request.status != "PENDING":
            raise ValidationError(
                {"detail": "You can only resend notifications for pending requests."}
            )

        now = timezone.now()

        # Checking the 1 hour limit
        if doc_request.last_sent_at and now < doc_request.last_sent_at + timedelta(
            hours=1
        ):
            time_left = (doc_request.last_sent_at + timedelta(hours=1)) - now
            minutes_left = int(time_left.total_seconds() // 60)
            raise ValidationError(
                {
                    "detail": (
                        "You can resend notification once per hour. "
                        f"Please wait {minutes_left} more minutes."
                    )
                }
            )

        # If the check is passed, we update the last send time
        doc_request.last_sent_at = now
        doc_request.save(update_fields=["last_sent_at"])

        # trigger Celery
        send_document_request_email_task.delay(doc_request.id)

        return doc_request

    @staticmethod
    def expire_prolonged_requests() -> int:
        """
        Finds all PENDING requests that have expired and
        sets their status to EXPIRED.
        Returns the number of updated records.
        """
        now = timezone.now()

        # We update all expired requests in one transaction.
        updated_count = DocumentRequest.objects.filter(
            status="PENDING", expires_at__lt=now
        ).update(status="EXPIRED")

        return updated_count

    @staticmethod
    @transaction.atomic
    def delete_document(document: Document) -> None:
        """
        Deletes a document. If the document being deleted was ACTIVE,
        finds the latest REPLACED version for this user and type,
        and restores its status to ACTIVE.
        """
        was_active = document.status == "ACTIVE"
        user = document.user
        doc_type = document.document_type

        # First, we delete the document itself.
        document.delete()

        # If it was active, we look for a replacement inside the same "folder"
        if was_active:
            latest_replaced = (
                Document.objects.filter(
                    user=user, document_type=doc_type, status="REPLACED"
                )
                .order_by("-created")
                .first()
            )

            if latest_replaced:
                latest_replaced.status = "ACTIVE"
                latest_replaced.save(update_fields=["status"])
