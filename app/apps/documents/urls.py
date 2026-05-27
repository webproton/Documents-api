# apps/documents/urls.py

from apps.documents.views import (
    AnonymousDocumentUploadAPIView,
    DocumentFolderViewSet,
    DocumentRequestAPIView,
    DocumentUploadAPIView,
)
from django.urls import include, path
from rest_framework.routers import DefaultRouter

app_name = "apps.documents"

# Initialize DefaultRouter for ViewSets
router = DefaultRouter()
router.register(r"folders", DocumentFolderViewSet, basename="folder")

urlpatterns = [
    path("upload/", DocumentUploadAPIView.as_view(), name="upload"),
    path("requests/", DocumentRequestAPIView.as_view(), name="request-create"),
    # Anon endpoint with token
    path(
        "upload/<uuid:token>/",
        AnonymousDocumentUploadAPIView.as_view(),
        name="anonymous-upload",
    ),
    # Router generated CRUD endpoints (includes /folders/ and /folders/<id>/)
    path("", include(router.urls)),
]
