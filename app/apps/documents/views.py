# apps/documents/views.py
from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
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
from rest_framework.views import APIView

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
from app.apps.notifications.tasks import send_notification_email_task

document_upload_parameters = [
    openapi.Parameter(
        "name",
        openapi.IN_FORM,
        description="Document name",
        type=openapi.TYPE_STRING,
        required=True,
    ),
    openapi.Parameter(
        "document_type",
        openapi.IN_FORM,
        description="Document type ID",
        type=openapi.TYPE_INTEGER,
        required=True,
    ),
    openapi.Parameter(
        "expiration_date",
        openapi.IN_FORM,
        description="Document expiration date",
        type=openapi.TYPE_STRING,
        format="date",
        required=True,
    ),
    openapi.Parameter(
        "file",
        openapi.IN_FORM,
        description="Document file (xls, csv, pdf)",
        type=openapi.TYPE_FILE,
        required=True,
    ),
]


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
        responses={
            200: openapi.Response(
                description="Notification resent successfully.",
                examples={
                    "application/json": {"detail": "Notification resent successfully."}
                },
            ),
            400: "You can resend notification once per hour.",
        },
    )
    @action(detail=True, methods=["post"], url_path="resend", url_name="resend")
    def resend_notification(self, request, pk=None):
        """POST /api/documents/requests/{id}/resend/"""
        doc_request = self.get_object()
        if (
            doc_request.last_sent_at
            and timezone.now() - doc_request.last_sent_at < timedelta(hours=1)
        ):
            raise serializers.ValidationError(
                {"detail": "You can resend notification once per hour."}
            )

        with transaction.atomic():
            doc_request.last_sent_at = timezone.now()
            doc_request.save(update_fields=["last_sent_at"])

            # Sending a new task strictly after a successful transaction commit
            transaction.on_commit(
                lambda: send_notification_email_task.delay(
                    recipient_email=doc_request.recipient_email,
                    context=doc_request.get_email_context(),  # take a pure context
                    notification_code="DOCUMENT_REQUEST",
                    title=f"Document Request: {doc_request.document_type.name}",
                    user_id=doc_request.requester.id,
                    document_id=doc_request.id,
                )
            )

        return Response(
            {"detail": "Notification resent successfully."}, status=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        operation_summary="Cancel document request",
        request_body=no_body,
        responses={
            200: openapi.Response(
                description="Document request has been canceled.",
                examples={
                    "application/json": {
                        "detail": "Document request has been canceled."
                    }
                },
            ),
            400: "Request cannot be canceled in its current status.",
        },
    )
    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    def cancel_request(self, request, pk=None):
        """POST /api/documents/requests/{id}/cancel/"""
        doc_request = self.get_object()

        if doc_request.status != DocumentRequest.STATUS.PENDING:
            raise serializers.ValidationError(
                {"detail": f"Cannot cancel a request with status {doc_request.status}."}
            )

        doc_request.status = DocumentRequest.STATUS.CANCELED
        doc_request.save(update_fields=["status"])

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


class DocumentUploadAPIView(APIView):
    """
    API Endpoint for authenticated users to upload documents.
    Delegates file processing and version control to DocumentService.
    IsAuthenticated is used by default in the settings
    """

    # Enable DRF to parse multi-part form data (required for file uploads)
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="Upload document",
        operation_description=(
            "Upload a document to the authenticated user's document list."
        ),
        manual_parameters=document_upload_parameters,
        responses={
            201: DocumentUploadSerializer,
            400: "Validation error.",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
