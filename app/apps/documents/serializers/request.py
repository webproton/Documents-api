# app/apps/documents/serializers/request.py

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import DocumentRequest, DocumentType
from app.config.settings import DOCUMENT_REQUEST_EXPIRATION_DAYS


class DocumentRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer to validate incoming document request data.
    Ensures recipient email is valid and the requested DocumentType exists.
    """

    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        error_messages={"does_not_exist": "Selected document type does not exist."},
    )

    class Meta:
        model = DocumentRequest
        fields = ["id", "recipient_email", "document_type", "token", "expires_at"]
        read_only_fields = ["id", "token", "expires_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        now = timezone.now()
        expiration_deadline = timezone.now() + timedelta(
            days=int(DOCUMENT_REQUEST_EXPIRATION_DAYS)
        )

        instance = DocumentRequest.objects.create(
            requester=user,
            expires_at=expiration_deadline,
            last_sent_at=now,
            **validated_data,
        )

        from app.apps.documents.tasks import send_document_request_email_task

        transaction.on_commit(
            lambda: send_document_request_email_task.delay(instance.id)
        )
        return instance


class DocumentRequestSerializer(serializers.ModelSerializer):
    """Serializer for DISPLAYING the full request data"""

    document_type_name = serializers.CharField(
        source="document_type.name", read_only=True
    )

    class Meta:
        model = DocumentRequest
        fields = [
            "id",
            "recipient_email",
            "document_type",
            "document_type_name",
            "token",
            "status",
            "created",
            "expires_at",
            "last_sent_at",
        ]
        read_only_fields = fields
