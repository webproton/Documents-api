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


class DocumentRequestSerializer(serializers.ModelSerializer):
    """Сериализатор для ОТОБРАЖЕНИЯ полных данных запроса (отдается наружу)"""

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
