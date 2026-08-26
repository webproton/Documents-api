# app/apps/documents/serializers/anonymous_document.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import Document
from app.apps.documents.models.document_request import DocumentRequest
from app.apps.documents.serializers.mixins import (
    CheckDocumentLimitSerializerMixin,
    DocumentFileValidationMixin,
)

User = get_user_model()


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

        # We save the request object in the class
        # context to avoid repeating the request in create()
        self.doc_request = doc_request
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        doc_request_instance = self.doc_request
        # Single LOCK ANCHOR: Lock the owner user.
        # Now ALL operations with this user's documents will follow each other,
        # which completely eliminates the possibility
        # of Deadlock between different tables.
        user = User.objects.select_for_update().get(
            pk=doc_request_instance.requester_id
        )

        # lock the query string for updating
        doc_request = DocumentRequest.objects.select_for_update().get(
            pk=doc_request_instance.pk
        )
        if doc_request.status != DocumentRequest.STATUS.PENDING:
            raise serializers.ValidationError(
                {"token": f"This request is already {doc_request.status.lower()}."}
            )

        # Check the limit inside the atomic block
        # (protection against limit breakout)
        self.validate_document_upload_limit(user)

        # Standard versioning: update previous
        # documents of the requester to REPLACED
        Document.objects.filter(
            user=user,
            document_type=doc_request.document_type,
            status=Document.STATUS.ACTIVE,
        ).update(status=Document.STATUS.REPLACED)

        # Set name
        name = validated_data.get("name") or validated_data["file"].name

        # Create the incoming document linked to the request owner
        new_document = Document.objects.create(
            user=user,
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
