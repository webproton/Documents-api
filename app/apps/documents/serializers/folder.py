# app/apps/documents/serializers/folder.py

from rest_framework import serializers

from app.apps.documents.models import Document, DocumentType


class FolderDocumentSerializer(serializers.ModelSerializer):
    """
    Simplified serializer to represent documents inside a specific folder.
    """

    class Meta:
        model = Document
        fields = ["id", "name", "file", "status", "expiration_date", "created"]


class FolderListSerializer(serializers.ModelSerializer):
    """
    Serializes DocumentType as a 'Folder' and dynamically injects
    only the requesting user's documents.
    """

    documents = serializers.SerializerMethodField()

    class Meta:
        model = DocumentType
        fields = ["id", "name", "description", "documents"]

    def get_documents(self, obj):
        # Access the authenticated user from the request context
        user = self.context["request"].user

        # Filter documents: must belong
        # to this user and match this folder's document type
        user_documents = Document.objects.filter(user=user, document_type=obj).order_by(
            "-created"
        )

        return FolderDocumentSerializer(user_documents, many=True).data
