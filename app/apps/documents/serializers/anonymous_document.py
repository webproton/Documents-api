# app/apps/documents/serializers/anonymous_document.py

import os

from django.conf import settings
from rest_framework import serializers

from app.apps.documents.models import Document


class AnonymousDocumentUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for unauthenticated external users uploading a file via token.
    Only requires the file itself; name is optional.
    """

    name = serializers.CharField(required=False, max_length=255)

    class Meta:
        model = Document
        fields = ["name", "file", "expiration_date"]

    def validate_file(self, value):
        # File size check
        max_size = getattr(settings, "DOCUMENT_MAX_SIZE", 10 * 1024 * 1024)
        if value.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File size exceeds the allowed limit of {max_size_mb}MB."
            )

        # Extension check
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
