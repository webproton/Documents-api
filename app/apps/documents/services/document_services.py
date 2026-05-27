# apps/documents/services/document_services.py
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from app.apps.documents.models import Document, DocumentRequest


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

        return doc_request
