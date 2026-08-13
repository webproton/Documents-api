# app/apps/documents/tests/test_documents.py
import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.documents.models import Document
from app.apps.documents.tests.factories import DocumentFactory, DocumentTypeFactory


@pytest.fixture
def test_data(user, user_factory):
    """Fixture to populate the database with test data using factories."""
    other_user = user_factory()

    # Create Document Types (Folders)
    type_passport = DocumentTypeFactory(
        name="Passport", description="Identity document"
    )
    type_visa = DocumentTypeFactory(name="Visa", description="Travel visa document")
    # This folder must remain empty to test that it gets hidden
    DocumentTypeFactory(name="Empty Folder", description="No documents here")

    # Current user's documents
    DocumentFactory(
        name="My Main Passport",
        user=user,
        document_type=type_passport,
        status=Document.STATUS.ACTIVE,
        expiration_date="2026-12-31",
    )
    DocumentFactory(
        name="Old Expired Passport",
        user=user,
        document_type=type_passport,
        status=Document.STATUS.REPLACED,
        expiration_date="2024-01-01",
    )
    DocumentFactory(
        name="Schengen Visa",
        user=user,
        document_type=type_visa,
        status=Document.STATUS.ACTIVE,
        expiration_date="2026-06-30",
    )

    # Foreign user's document to test strict data isolation
    DocumentFactory(
        name="Secret File",
        user=other_user,
        document_type=type_visa,
        status=Document.STATUS.ACTIVE,
    )

    return {
        "type_passport": type_passport,
    }


@pytest.mark.django_db
class TestDocumentSearchAndFilters:

    def test_document_type_list_and_search(self, api_client, user, test_data):
        """Ensure any authenticated user can view and search all document types."""
        api_client.force_authenticate(user=user)
        url = reverse("apps.documents:document-type-list")

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

        response = api_client.get(url, {"search": "Identity"})
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Passport"

    def test_folder_list_hides_empty_and_foreign_folders(
        self, api_client, user, test_data
    ):
        """Verify folder list excludes empty folders and other users' documents."""
        api_client.force_authenticate(user=user)
        url = reverse("apps.documents:folder-list")

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

        passport_folder = next(f for f in response.data if f["name"] == "Passport")
        assert len(passport_folder["documents"]) == 1
        assert passport_folder["documents"][0]["name"] == "My Main Passport"

    def test_folder_list_search_and_ordering(self, api_client, user, test_data):
        """Verify search by document name and ordering by folder name work correctly."""
        api_client.force_authenticate(user=user)
        url = reverse("apps.documents:folder-list")

        response = api_client.get(url, {"search": "Schengen"})
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Visa"

        response = api_client.get(url, {"ordering": "-name"})
        assert response.data[0]["name"] == "Visa"
        assert response.data[1]["name"] == "Passport"

    def test_all_documents_action_returns_history(self, api_client, user, test_data):
        """
        Verify the custom action returns all documents
        within a folder, including replaced ones
        ."""
        api_client.force_authenticate(user=user)

        passport_type_id = test_data["type_passport"].id
        url = reverse(
            "apps.documents:folder-all-documents", kwargs={"pk": passport_type_id}
        )

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_all_documents_expiration_date_filter(self, api_client, user, test_data):
        """Verify filtering documents by precise
        expiration date works inside the folder history."""
        api_client.force_authenticate(user=user)

        passport_type_id = test_data["type_passport"].id
        url = reverse(
            "apps.documents:folder-all-documents", kwargs={"pk": passport_type_id}
        )

        response = api_client.get(
            url,
            {"expiration_date_from": "2026-12-01", "expiration_date_to": "2026-12-31"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["name"] == "My Main Passport"

    def test_folder_list_expiration_date_filter_valid(
        self, api_client, user, test_data
    ):
        """Verify filtering by a valid
        expiration date on the main folder list endpoint."""
        api_client.force_authenticate(user=user)
        url = reverse("apps.documents:folder-list")

        # Passport expires on 2026-12-31, Visa expires on 2026-06-30
        response = api_client.get(
            url,
            {"expiration_date_from": "2026-07-01", "expiration_date_to": "2026-12-31"},
        )
        assert response.status_code == status.HTTP_200_OK
        # Only the Passport folder should be returned
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Passport"

    def test_folder_list_expiration_date_filter_invalid(
        self, api_client, user, test_data
    ):
        """Ensure an invalid date format in folder
        list is gracefully ignored by parse_date."""
        api_client.force_authenticate(user=user)
        url = reverse("apps.documents:folder-list")

        # Passing an invalid date string
        response = api_client.get(url, {"expiration_date": "not-a-valid-date"})
        assert response.status_code == status.HTTP_200_OK
        # The filter should be skipped, returning both active folders
        assert len(response.data) == 2

    def test_all_documents_expiration_date_filter_invalid(
        self, api_client, user, test_data
    ):
        """Ensure an invalid date format
        inside folder history is gracefully ignored."""
        api_client.force_authenticate(user=user)

        passport_type_id = test_data["type_passport"].id
        url = reverse(
            "apps.documents:folder-all-documents", kwargs={"pk": passport_type_id}
        )

        # Passing an invalid date string to custom action
        response = api_client.get(url, {"expiration_date": "corrupted-date-format"})
        assert response.status_code == status.HTTP_200_OK
        # The filter should be skipped, returning the full history (2 documents)
        assert len(response.data) == 2
