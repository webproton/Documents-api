# apps/documents/tests/test_views.py

import uuid
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app.apps.documents.models import Document, DocumentRequest
from app.apps.documents.tests.factories import (
    DocumentFactory,
    DocumentRequestFactory,
    DocumentTypeFactory,
)


@pytest.mark.django_db
def test_authenticated_user_can_upload_document(api_client, user):
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory(name="Passport")
    url = reverse("apps.documents:upload")

    pdf_file = SimpleUploadedFile(
        "passport.pdf", b"dummy pdf content", content_type="application/pdf"
    )

    payload = {
        "name": "My New Passport",
        "document_type": doc_type.id,
        "file": pdf_file,
        "expiration_date": (timezone.now() + timedelta(days=365)).date(),
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "ACTIVE"
    assert Document.objects.filter(user=user, document_type=doc_type).count() == 1


@pytest.mark.django_db
def test_upload_new_version_replaces_old_document_status(api_client, user):
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory(name="Driver License")
    url = reverse("apps.documents:upload")

    old_doc = DocumentFactory(user=user, document_type=doc_type, status="ACTIVE")

    new_pdf = SimpleUploadedFile(
        "new_license.pdf", b"new content", content_type="application/pdf"
    )
    payload = {
        "name": "New Driver License",
        "document_type": doc_type.id,
        "file": new_pdf,
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED

    old_doc.refresh_from_db()
    assert old_doc.status == "REPLACED"

    new_doc_id = response.data["id"]
    assert Document.objects.get(id=new_doc_id).status == "ACTIVE"


@pytest.mark.django_db
def test_upload_fails_with_past_expiration_date(api_client, user):
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory()
    url = reverse("apps.documents:upload")

    past_date = (timezone.now() - timedelta(days=5)).date()
    pdf_file = SimpleUploadedFile(
        "test.pdf", b"content", content_type="application/pdf"
    )

    payload = {
        "name": "Expired Doc",
        "document_type": doc_type.id,
        "file": pdf_file,
        "expiration_date": past_date,
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "expiration_date" in response.data["errors"]


@pytest.mark.django_db
def test_upload_fails_with_invalid_file_extension(api_client, user):
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory()
    url = reverse("apps.documents:upload")

    malicious_file = SimpleUploadedFile(
        "virus.exe", b"malicious code", content_type="application/octet-stream"
    )

    payload = {
        "name": "Executable",
        "document_type": doc_type.id,
        "file": malicious_file,
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "file" in response.data["errors"]


@pytest.mark.django_db
def test_authenticated_user_can_list_folders_with_only_their_documents(
    api_client, user
):
    """
    Verify that the folder endpoint returns document
    types and separates user data securely.
    """
    api_client.force_authenticate(user=user)

    # Arrange: Create a folder (DocumentType)
    contract_type = DocumentTypeFactory(name="Contracts")

    # Create a document belonging to our user
    user_doc = DocumentFactory(
        user=user, document_type=contract_type, name="User Contract"
    )

    # Create a document belonging to another random user (should be isolated)
    other_user_doc = DocumentFactory(
        document_type=contract_type, name="Strangers Contract"
    )

    url = reverse("apps.documents:folder-list")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK

    # Find our "Contracts" folder in the list
    contracts_folder = next(
        folder for folder in response.data if folder["id"] == contract_type.id
    )
    assert contracts_folder["name"] == "Contracts"

    # Verify mapping: user's document is inside, stranger's document is hidden
    extracted_doc_ids = [doc["id"] for doc in contracts_folder["documents"]]
    assert user_doc.id in extracted_doc_ids
    assert other_user_doc.id not in extracted_doc_ids


@pytest.mark.django_db
def test_unauthenticated_user_cannot_list_folders(api_client):
    """
    Ensure anonymous requests to the folders endpoint are blocked.
    """
    url = reverse("apps.documents:folder-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_authenticated_user_can_create_document_request(api_client, user):
    """
    Ensure an authenticated user can create a document request.
    Verifies that a unique token is returned and expiration is set properly.
    """
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory(name="Tax Return")
    url = reverse("apps.documents:document-request-list")

    payload = {"recipient_email": "client@example.com", "document_type": doc_type.id}

    response = api_client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert "token" in response.data
    assert "expires_at" in response.data

    # Check database record consistency
    db_request = DocumentRequest.objects.get(id=response.data["id"])
    assert db_request.requester == user
    assert db_request.recipient_email == "client@example.com"
    assert db_request.document_type == doc_type
    assert db_request.token is not None


@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_document_request(api_client):
    """
    Verify that anonymous users are blocked from creating document requests.
    """
    url = reverse("apps.documents:document-request-list")
    payload = {"recipient_email": "client@example.com", "document_type": 1}

    response = api_client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_anonymous_user_can_upload_document_via_valid_token(api_client, user):
    """
    Ensure an unauthenticated agent can fulfill a request with a valid token.
    The resulting document must belong to the user who requested it.
    """
    doc_type = DocumentTypeFactory(name="Tax Certificate")
    # Create request token in the database
    doc_request = DocumentRequestFactory(
        requester=user, document_type=doc_type, status="PENDING"
    )

    url = reverse(
        "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
    )
    pdf_file = SimpleUploadedFile(
        "tax.pdf", b"tax content", content_type="application/pdf"
    )

    payload = {"name": "External Tax Document", "file": pdf_file}

    # Execute request completely unauthenticated
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "ACTIVE"

    # CHECK: Request status should change to COMPLETED
    doc_request.refresh_from_db()
    assert doc_request.status == "COMPLETED"

    # Confirm Document creation and ownership linkage
    uploaded_doc = Document.objects.get(id=response.data["id"])
    assert uploaded_doc.user == user
    assert uploaded_doc.document_type == doc_type


@pytest.mark.django_db
def test_anonymous_upload_fails_if_request_already_completed(api_client, user):
    """
    check that if the request is already COMPLETED, the file cannot be downloaded again
    """
    doc_type = DocumentTypeFactory()
    # Создаем уже завершенный запрос
    doc_request = DocumentRequestFactory(
        requester=user, document_type=doc_type, status="COMPLETED"
    )

    url = reverse(
        "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
    )
    pdf_file = SimpleUploadedFile(
        "invoice.pdf", b"content", content_type="application/pdf"
    )

    payload = {"file": pdf_file}
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "token" in response.data["errors"]

    error_message = str(response.data["errors"]["token"]).lower()
    assert "completed" in error_message


@pytest.mark.django_db
def test_anonymous_upload_fails_with_expired_token(api_client, user):
    """
    Verify that an error is thrown if the 30-day window has expired.
    """
    doc_type = DocumentTypeFactory()
    # Create an already expired token link
    expired_date = timezone.now() - timedelta(days=1)
    doc_request = DocumentRequestFactory(
        requester=user, document_type=doc_type, expires_at=expired_date
    )

    url = reverse(
        "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
    )
    pdf_file = SimpleUploadedFile(
        "tax.pdf", b"tax content", content_type="application/pdf"
    )

    payload = {"file": pdf_file}
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "token" in response.data["errors"]


@pytest.mark.django_db
def test_anonymous_upload_fails_with_invalid_token(api_client):
    """
    Verify that a completely random token fails with a 400 Bad Request error.
    """
    random_token = uuid.uuid4()
    url = reverse("apps.documents:anonymous-upload", kwargs={"token": random_token})
    pdf_file = SimpleUploadedFile(
        "tax.pdf", b"tax content", content_type="application/pdf"
    )

    payload = {"file": pdf_file}
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "detail" in response.data["errors"]
