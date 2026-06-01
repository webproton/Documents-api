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

    documents = FolderDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentType
        fields = ["id", "name", "description", "documents"]
