# apps/documents/views.py

from apps.documents.services.document_services import DocumentService
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.documents.models import DocumentRequest, DocumentType
from app.apps.documents.serializers import (
    AnonymousDocumentUploadSerializer,
    DocumentRequestCreateSerializer,
    DocumentRequestSerializer,
    DocumentUploadSerializer,
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
        serializer = AnonymousDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        # Pass token extracted from the URL path down to the service layer
        document = DocumentService.handle_anonymous_upload(
            token=token,
            file=validated_data["file"],
            name=validated_data.get("name"),
            expiration_date=validated_data.get("expiration_date"),
        )

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
    """

    queryset = DocumentRequest.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentRequestCreateSerializer
        return DocumentRequestSerializer

    def perform_destroy(self, instance):
        # Instead of the standard instance.delete() we call our service
        DocumentService.delete_document(instance)

    def create(self, request, *args, **kwargs):
        """POST /api/documents/requests/"""
        serializer = DocumentRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        # Delegate token generation and database execution to the Service Layer
        doc_request = DocumentService.create_document_request(
            user=request.user,
            recipient_email=validated_data["recipient_email"],
            document_type=validated_data["document_type"],
        )
        response_serializer = DocumentRequestSerializer(doc_request)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="resend", url_name="resend")
    def resend_notification(self, request, pk=None):
        """POST /api/documents/requests/{id}/resend/"""
        doc_request = self.get_object()
        DocumentService.resend_document_request(doc_request=doc_request)
        return Response(
            {"detail": "Notification resent successfully."}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    def cancel_request(self, request, pk=None):
        """POST /api/documents/requests/{id}/cancel/"""
        doc_request = self.get_object()
        DocumentService.cancel_document_request(doc_request=doc_request)
        return Response(
            {"detail": "Document request has been canceled."}, status=status.HTTP_200_OK
        )


class DocumentFolderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows folders (DocumentTypes) to be viewed.
    Automatically provides 'list' and 'retrieve' actions.
    """

    queryset = DocumentType.objects.all().order_by("name")
    serializer_class = FolderListSerializer


class DocumentUploadAPIView(APIView):
    """
    API Endpoint for authenticated users to upload documents.
    Delegates file processing and version control to DocumentService.
    """

    # Enable DRF to parse multi-part form data (required for file uploads)
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        # Step 1: Pass request data into the serializer
        #  for structural and format validation
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        # Step 2: Delegate the business action
        # (creation & version replacement) to the Service Layer
        document = DocumentService.create_document(
            user=request.user,
            name=validated_data["name"],
            file=validated_data["file"],
            document_type=validated_data["document_type"],
            expiration_date=validated_data.get("expiration_date"),
        )

        # Step 3: Return a clean, successful production response
        return Response(
            {
                "message": "Document uploaded successfully.",
                "document_id": document.id,
                "status": document.status,
            },
            status=status.HTTP_201_CREATED,
        )
