# apps/documents/views.py
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from drf_yasg import openapi
from drf_yasg.utils import no_body, swagger_auto_schema
from rest_framework import (
    filters,
    generics,
    mixins,
    permissions,
    serializers,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from app.apps.documents.filters import DocumentFilter
from app.apps.documents.models import Document, DocumentRequest, DocumentType
from app.apps.documents.serializers import (
    AnonymousDocumentUploadSerializer,
    DocumentRequestCreateSerializer,
    DocumentRequestSerializer,
    DocumentTypePublicSerializer,
    DocumentUpdateSerializer,
    DocumentUploadSerializer,
    FolderDocumentSerializer,
    FolderListSerializer,
)
from app.apps.documents.serializers.mixins import DetailMessageSerializer


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

        if getattr(self, "swagger_fake_view", False):
            return context

        context["doc_request"] = self.get_object()
        return context


class DocumentRequestViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    ViewSet for creating document requests.
    Allows creating new requests (POST) and viewing the list of sent requests (GET).
    IsAuthenticated is used by default in the settings
    """

    def get_queryset(self):
        """Return document requests created by the current user."""
        if getattr(self, "swagger_fake_view", False):
            return DocumentRequest.objects.none()
        return DocumentRequest.objects.filter(requester=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentRequestCreateSerializer
        return DocumentRequestSerializer

    @swagger_auto_schema(
        method="post",
        operation_summary="Resend document request notification",
        operation_description=(
            "Resend the notification email for a document request. "
            "A notification can be resent at most once per hour. "
            "No request body is required."
        ),
        request_body=no_body,
        responses={200: DetailMessageSerializer, 400: DetailMessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="resend", url_name="resend")
    def resend_notification(self, request, pk=None):
        """POST /api/documents/requests/{id}/resend/"""
        doc_request = self.get_object()
        try:
            doc_request.resend_notification()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"detail": e.message})

        return Response(
            {"detail": "Notification resent successfully."}, status=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        operation_summary="Cancel document request",
        request_body=no_body,
        responses={200: DetailMessageSerializer, 400: DetailMessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    def cancel_request(self, request, pk=None):
        """POST /api/documents/requests/{id}/cancel/"""
        doc_request = self.get_object()
        try:
            doc_request.cancel()
        except DjangoValidationError as e:
            # Convert the Django built-in error
            # to a DRF error for a 400 Bad Request response
            raise serializers.ValidationError({"detail": e.message})

        return Response(
            {"detail": "Document request has been canceled."}, status=status.HTTP_200_OK
        )


class DocumentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint for viewing document types by all users.
    Supports search via ?search=...
    """

    permission_classes = [permissions.IsAuthenticated]
    queryset = DocumentType.objects.all().order_by("name")
    serializer_class = DocumentTypePublicSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "description"]


class DocumentFolderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    managing user folders.
    Provides:
    - Retrieval of the folder list (containing only active documents)
    - Search, filtering, and sorting
    - Retrieval of ALL documents within a specific folder
    """

    serializer_class = FolderListSerializer

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    # Support searching by name or document type
    search_fields = ["documents__name", "name"]

    # Support sorting by creation date, name, or document type
    ordering_fields = ["documents__created", "name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentType.objects.none()

        user = self.request.user

        # get base qset user
        base_user_documents = Document.objects.filter(user=user)

        # pass it through a date range filter set
        filtered_documents = DocumentFilter(
            self.request.query_params, queryset=base_user_documents
        ).qs

        # Separate the logic for the folder list and the detailed view.
        if self.action == "list":
            # By default, only the active document in each folder is shown
            active_docs = filtered_documents.filter(
                status=Document.STATUS.ACTIVE
            ).order_by("-created")

            # Folders with no documents do not appear in the list
            return (
                DocumentType.objects.filter(
                    documents__in=active_docs,
                )
                .prefetch_related(Prefetch("documents", queryset=active_docs))
                .order_by("name")
                .distinct()
            )

        return DocumentType.objects.all().order_by("name")

    # It’s possible to get all documents in a specified folder
    # GET /api/documents/folders/{id}/all_documents/

    @swagger_auto_schema(
        operation_summary="List all documents in a folder",
        operation_description=(
            "Returns all documents, including active and replaced documents, "
            "for the specified folder."
        ),
        responses={
            200: openapi.Response(
                description="List of documents in the folder.",
                schema=FolderDocumentSerializer(many=True),
            ),
        },
    )
    @action(detail=True, methods=["get"], url_path="all-documents")
    def all_documents(self, request, pk=None):
        """Returns ALL documents (both active and replaced) for the specified folder."""
        folder = self.get_object()  # Get the current document type (folder).

        # users documents from this folder.
        documents = Document.objects.filter(
            user=request.user, document_type=folder
        ).order_by("-created")

        filtered_documents = DocumentFilter(request.query_params, queryset=documents).qs

        serializer = FolderDocumentSerializer(filtered_documents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentUploadAPIView(mixins.CreateModelMixin, generics.GenericAPIView):
    """
    API Endpoint for authenticated users to upload documents.
    Delegates file processing and version control to DocumentService.
    IsAuthenticated is used by default in the settings
    """

    # Enable DRF to parse multi-part form data (required for file uploads)
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = DocumentUploadSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save()


class DocumentViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for viewing, updating, and deleting specific documents.
    Only the owner can access their documents.
    """

    serializer_class = DocumentUpdateSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        # Strict isolation: the user sees and manages ONLY their own documents
        return Document.objects.filter(user=self.request.user)
