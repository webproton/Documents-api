# apps/documents/serializers/document.py
from django.db import transaction
from rest_framework import serializers

from app.apps.billing.models import Subscription
from app.apps.documents.models import Document, DocumentType
from app.apps.documents.serializers.mixins import (
    CheckDocumentLimitSerializerMixin,
    DocumentFileValidationMixin,
)


class DocumentUploadSerializer(
    CheckDocumentLimitSerializerMixin,
    DocumentFileValidationMixin,
    serializers.ModelSerializer,
):
    """
    Serializer handling user document uploads.
    Validates file extensions, size limits, and ensures the document type exists.
    """

    # Explicitly define document_type
    # as PrimaryKeyRelatedField to ensure strict validation
    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        error_messages={"does_not_exist": "Selected document type does not exist."},
    )

    class Meta:
        model = Document
        fields = ["id", "status", "name", "file", "document_type", "expiration_date"]
        read_only_fields = [
            "id",
            "status",
        ]

    def validate(self, attrs):
        user = self.context["request"].user
        self.validate_document_upload_limit(user)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        document_type = validated_data["document_type"]

        # Lock subscription to prevent concurrent uploads from bypassing the limit.
        subscription = Subscription.objects.select_for_update().get(user=user)
        # None means the plan has no document limit.
        limit = subscription.plan.document_limit if subscription.plan else None

        if limit is not None:
            # Count all documents, including replaced versions.
            total_documents = Document.objects.filter(user=user).count()

            if total_documents >= limit:
                raise serializers.ValidationError(
                    {
                        "document_type": [
                            f"Document limit reached ({limit}). "
                            "Upgrade your plan to upload more documents."
                        ]
                    }
                )
        # Lock active versions and replace them before creating the new version.
        Document.objects.select_for_update().filter(
            user=user, document_type=document_type, status=Document.STATUS.ACTIVE
        ).update(status=Document.STATUS.REPLACED)

        # Use the provided name or fall back to the uploaded filename.
        name = validated_data.get("name") or validated_data["file"].name

        return Document.objects.create(
            user=user,
            name=name,
            file=validated_data["file"],
            document_type=document_type,
            expiration_date=validated_data.get("expiration_date"),
            status=Document.STATUS.ACTIVE,
        )


class DocumentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating an existing document.
    Allows changing ONLY the name and expiration date.
    """

    class Meta:
        model = Document
        fields = ["id", "name", "status", "document_type", "expiration_date", "file"]
        read_only_fields = ["id", "status", "document_type", "file"]


class DocumentTypePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ["id", "name", "description", "template"]
