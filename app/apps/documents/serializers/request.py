# app/apps/documents/serializers/request.py

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
