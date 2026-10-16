# app/apps/documents/serializers/anonymous_document.py
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import Document
from app.apps.documents.models.document_request import DocumentRequest
from app.apps.documents.serializers.document import DocumentTypePublicSerializer
from app.apps.documents.serializers.mixins import (
    CheckDocumentLimitSerializerMixin,
    DocumentFileValidationMixin,
)


class AnonymousDocumentUploadSerializer(
    CheckDocumentLimitSerializerMixin,
    DocumentFileValidationMixin,
    serializers.ModelSerializer,
):
    """
    Serializer for unauthenticated external users uploading a file via token.
    Only requires the file itself; name is optional.
    """

    name = serializers.CharField(required=False, max_length=255)

    class Meta:
        model = Document
        fields = ["id", "name", "file", "status", "expiration_date"]
        read_only_fields = ["id", "status"]

    def validate(self, attrs):
        doc_request = self.context.get("doc_request")

        # Check if the 30-day link has already expired
        if doc_request.expires_at < timezone.now():
            raise serializers.ValidationError(
                {"token": "This secure upload link has expired."}
            )
        # Check status requests (should be PENDING only)
        if doc_request.status != DocumentRequest.STATUS.PENDING:
            raise serializers.ValidationError(
                {"token": f"This request is already {doc_request.status.lower()}."}
            )
        self.validate_document_upload_limit(doc_request.requester)

        # We save the request object in the class
        # context to avoid repeating the request in create()
        self.doc_request = doc_request
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # lock the query string for updating
        doc_request = self.doc_request

        # Standard versioning: update previous
        # documents of the requester to REPLACED
        Document.objects.select_for_update().filter(
            user=doc_request.requester,
            document_type=doc_request.document_type,
            status=Document.STATUS.ACTIVE,
        ).update(status=Document.STATUS.REPLACED)

        # Set name
        name = validated_data.get("name") or validated_data["file"].name

        # Create the incoming document linked to the request owner
        new_document = Document.objects.create(
            user=doc_request.requester,
            name=name,
            file=validated_data["file"],
            document_type=doc_request.document_type,
            expiration_date=validated_data.get("expiration_date"),
            status=Document.STATUS.ACTIVE,
        )
        # Change  the request status  to COMPLETED
        # close the request
        doc_request.status = DocumentRequest.STATUS.COMPLETED
        doc_request.save(update_fields=["status"])

        return new_document


class DocumentRequestPublicSerializer(serializers.ModelSerializer):
    """
    What the recipient of an upload link may see before uploading:
    the requested type, who asked, and whether the link still works.
    """

    document_type = DocumentTypePublicSerializer(read_only=True)
    requester_email = serializers.EmailField(source="requester.email", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = ["document_type", "requester_email", "status", "expires_at"]
        read_only_fields = fields

    def get_status(self, obj) -> str:
        """PENDING links past expires_at are already unusable — report EXPIRED
        even before the daily expiration task updates the row."""
        if (
            obj.status == DocumentRequest.STATUS.PENDING
            and obj.expires_at
            and obj.expires_at < timezone.now()
        ):
            return DocumentRequest.STATUS.EXPIRED
        return obj.status
