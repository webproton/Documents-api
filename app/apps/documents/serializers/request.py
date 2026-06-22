# app/apps/documents/serializers/request.py

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.apps.documents.models import DocumentRequest, DocumentType


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

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        now = timezone.now()
        expiration_deadline = timezone.now() + timedelta(
            days=int(getattr(settings, "DOCUMENT_REQUEST_EXPIRATION_DAYS", 30))
        )
        instance = DocumentRequest.objects.create(
            requester=user,
            expires_at=expiration_deadline,
            last_sent_at=now,
            **validated_data,
        )

        from app.apps.notifications.tasks import send_notification_email_task

        transaction.on_commit(
            lambda: send_notification_email_task.delay(
                recipient_email=instance.recipient_email,
                context=instance.get_email_context(),
                notification_code="DOCUMENT_REQUEST",  # defining a template
                title=f"Document Request: {instance.document_type.name}",
                user_id=instance.requester.id,
                document_id=instance.id,
            )
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
