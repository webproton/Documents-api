# app/apps/documents/serializers/mixins.py

import os

from django.conf import settings
from rest_framework import serializers


class DocumentFileValidationMixin:
    """
    Mixin to provide reusable file size and extension validation
    for document serializers.
    """

    def validate_file(self, value):
        # 1. Checking file size
        max_size = getattr(settings, "DOCUMENT_MAX_SIZE", 10 * 1024 * 1024)
        if value.size > max_size:
            max_size_mb = int(max_size / (1024 * 1024))
            raise serializers.ValidationError(
                f"File size exceeds the allowed limit of {max_size_mb}MB."
            )

        # 2. Checking the file extension
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
