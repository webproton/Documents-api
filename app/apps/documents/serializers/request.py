# app/apps/documents/serializers/request.py

from datetime import timedelta

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
        fields = ["recipient_email", "document_type"]

    def create(self, validated_data):
        user = self.context["request"].user
        expiration_deadline = timezone.now() + timedelta(days=30)

        return DocumentRequest.objects.create(
            requester=user, expires_at=expiration_deadline, **validated_data
        )
