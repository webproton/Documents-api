# app/apps/documents/serializers/mixins.py

import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from app.apps.documents.models import Document


class CheckDocumentLimitSerializerMixin:
    """
    Mixin that validates the user hasn't exceeded their plan's
    document upload limit.

    Counts ALL documents ever uploaded by the user (both ACTIVE and
    REPLACED) — counting only ACTIVE documents would let a user upload
    unlimited documents by repeatedly replacing the same folder.
    """

    def validate_document_upload_limit(self, user):
        try:
            plan = user.subscription.plan
        except ObjectDoesNotExist:
            plan = None

        limit = plan.document_limit if plan else None
        if limit is None:
            return  # unlimited or no plan configured

        # count all the documents of this user in the database
        # — without filtering by status.
        # That is, both ACTIVE and REPLACED
        total_documents = Document.objects.filter(user=user).count()

        # If the user already has more or equal
        # to the limit of documents, block the upload
        if total_documents >= limit:
            raise serializers.ValidationError(
                {
                    "document_type": [
                        f"Document limit reached ({limit}). "
                        "Upgrade your plan to upload more documents."
                    ]
                }
            )


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
