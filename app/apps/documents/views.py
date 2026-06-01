# apps/documents/views.py

from apps.documents.serializers.document import DocumentUploadSerializer
from django.db.models import Prefetch
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.documents.models import Document, DocumentRequest, DocumentType
from app.apps.documents.serializers import (
    AnonymousDocumentUploadSerializer,
    DocumentRequestCreateSerializer,
    FolderListSerializer,
)


class AnonymousDocumentUploadAPIView(generics.GenericAPIView):
    """
    Public endpoint for external users to upload documents safely
    using a unique URL token. Does not require authentication headers.
    """

    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    lookup_field = "token"
    # which field to search for the request object
    queryset = DocumentRequest.objects.select_related("document_type", "requester")
    serializer_class = AnonymousDocumentUploadSerializer

    def post(self, request, token, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_serializer_context(self):
        """
        pass  found DocumentRequest object to serializer.
        self.get_object() uses lookup_field="token" , return  404
        if token in the url is invalid
        """
        context = super().get_serializer_context()
        context["doc_request"] = self.get_object()
        return context


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
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
