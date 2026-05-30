# apps/documents/views.py

from apps.documents.serializers.document import DocumentUploadSerializer
from django.db.models import Prefetch
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.documents.models import Document, DocumentRequest, DocumentType
from app.apps.documents.serializers import (
    AnonymousDocumentUploadSerializer,
    DocumentRequestCreateSerializer,
    FolderListSerializer,
)


class AnonymousDocumentUploadAPIView(APIView):
    """
    Public endpoint for external users to upload documents safely
    using a unique URL token. Does not require authentication headers.
    """

    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, token, *args, **kwargs):
        serializer = AnonymousDocumentUploadSerializer(
            data=request.data, context={"token": token}
        )
        serializer.is_valid(raise_exception=True)

        # Pass token extracted from the URL path down to the service layer
        document = serializer.save()

        return Response(
            {
                "message": "Document uploaded successfully via secure token.",
                "document_id": document.id,
                "status": document.status,
            },
            status=status.HTTP_201_CREATED,
        )


class DocumentRequestViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for creating document requests.
    Uses GenericViewSet + CreateModelMixin to expose EXCLUSIVELY the POST method.
    IsAuthenticated is used by default in the settings
    """

    queryset = DocumentRequest.objects.all()
    serializer_class = DocumentRequestCreateSerializer

    def create(self, request, *args, **kwargs):
        """POST /api/documents/requests/"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_request = serializer.save()

        return Response(
            {
                "message": "Document request created successfully.",
                "id": doc_request.id,
                "token": doc_request.token,
                "expires_at": doc_request.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class DocumentFolderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows folders (DocumentTypes) to be viewed.
    Automatically provides 'list' and 'retrieve' actions.
    IsAuthenticated is used by default in the settings
    """

    serializer_class = FolderListSerializer

    def get_queryset(self):

        # prefetch_related with an explicit Queryset perfectly
        # filters the current user's documents with just one additional query.
        return DocumentType.objects.prefetch_related(
            Prefetch(
                "documents",
                queryset=Document.objects.filter(user=self.request.user).order_by(
                    "-created"
                ),
            )
        ).order_by("name")


class DocumentUploadAPIView(APIView):
    """
    API Endpoint for authenticated users to upload documents.
    Delegates file processing and version control to DocumentService.
    IsAuthenticated is used by default in the settings
    """

    # Enable DRF to parse multi-part form data (required for file uploads)
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        document = serializer.save()

        return Response(
            {
                "message": "Document uploaded successfully.",
                "document_id": document.id,
                "status": document.status,
            },
            status=status.HTTP_201_CREATED,
        )
