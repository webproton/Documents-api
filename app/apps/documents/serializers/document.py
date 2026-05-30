# apps/documents/serializers/document.py
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import Document, DocumentType
from app.apps.documents.serializers.mixins import DocumentFileValidationMixin


class DocumentUploadSerializer(
    DocumentFileValidationMixin, serializers.ModelSerializer
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
        fields = ["name", "file", "document_type", "expiration_date"]

    def validate(self, attrs):
        expiration_date = attrs.get("expiration_date")
        if expiration_date and expiration_date < timezone.now().date():
            raise serializers.ValidationError(
                {"expiration_date": "The expiration date cannot be in the past."}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        document_type = validated_data["document_type"]

        with transaction.atomic():
            # Capturing and replacing old versions
            Document.objects.select_for_update().filter(
                user=user, document_type=document_type, status="ACTIVE"
            ).update(status="REPLACED")

            name = validated_data.get("name") or validated_data["file"].name

            return Document.objects.create(
                user=user,
                name=name,
                file=validated_data["file"],
                document_type=document_type,
                expiration_date=validated_data.get("expiration_date"),
                status="ACTIVE",
            )
