# apps/documents/serializers/document.py

import os

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import Document, DocumentType


class DocumentUploadSerializer(serializers.ModelSerializer):
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

    def validate_file(self, value):
        """
        Validates the uploaded file's size and extension.
        """
        # 1. Check file size
        max_size = getattr(
            settings, "DOCUMENT_MAX_SIZE", 10 * 1024 * 1024
        )  # Default 10MB
        if value.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File size exceeds the allowed limit of {max_size_mb}MB."
            )

        # 2. Check file extension
        ext = os.path.splitext(value.name)[1].lower()
        allowed_extensions = getattr(
            settings, "ALLOWED_DOCUMENT_EXTENSIONS", [".pdf", ".xls", ".xlsx", ".csv"]
        )
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                "Unsupported file format. Allowed formats are: "
                f"{', '.join(allowed_extensions)}."
            )

        return value

    def validate(self, attrs):
        """
        Cross-field validation (Task 9: expiration_date >= today).
        """
        expiration_date = attrs.get("expiration_date")
        if expiration_date and expiration_date < timezone.now().date():
            raise serializers.ValidationError(
                {"expiration_date": "The expiration date cannot be in the past."}
            )

        return attrs
