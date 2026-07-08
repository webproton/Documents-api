# apps/documents/urls.py

from apps.documents.views import (
    AnonymousDocumentUploadAPIView,
    DocumentFolderViewSet,
    DocumentRequestViewSet,
    DocumentTypeViewSet,
    DocumentUploadAPIView,
    DocumentViewSet,
)
from django.urls import include, path
from rest_framework.routers import DefaultRouter

app_name = "apps.documents"

# Initialize DefaultRouter for ViewSets
router = DefaultRouter()
router.register(r"folders", DocumentFolderViewSet, basename="folder")
router.register(r"requests", DocumentRequestViewSet, basename="document-request")
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"types", DocumentTypeViewSet, basename="document-type")

urlpatterns = [
    path("upload/", DocumentUploadAPIView.as_view(), name="upload"),
    # Anon endpoint with token
    path(
        "upload/<uuid:token>/",
        AnonymousDocumentUploadAPIView.as_view(),
        name="anonymous-upload",
    ),
    # Router generated CRUD endpoints (includes /folders/ and /folders/<id>/)
    path("", include(router.urls)),
]
