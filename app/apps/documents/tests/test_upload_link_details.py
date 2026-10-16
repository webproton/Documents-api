"""Public details of an upload link (GET /api/documents/upload/<token>/)."""

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app.apps.documents.tests.factories import (
    DocumentRequestFactory,
    DocumentTypeFactory,
)


def details_url(token):
    return reverse("apps.documents:anonymous-upload", kwargs={"token": token})


@pytest.mark.django_db
def test_anyone_with_the_link_sees_what_is_requested(api_client, user):
    doc_type = DocumentTypeFactory(name="Passport", description="Main page scan")
    doc_request = DocumentRequestFactory(requester=user, document_type=doc_type)

    # No authentication: the recipient is anonymous
    response = api_client.get(details_url(doc_request.token))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["requester_email"] == user.email
    assert response.data["status"] == "PENDING"
    assert response.data["document_type"]["name"] == "Passport"
    assert response.data["document_type"]["description"] == "Main page scan"
    # The token itself and requester internals are not exposed
    assert "token" not in response.data
    assert "recipient_email" not in response.data


@pytest.mark.django_db
def test_past_deadline_is_reported_as_expired(api_client):
    doc_request = DocumentRequestFactory(
        status="PENDING", expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = api_client.get(details_url(doc_request.token))

    assert response.data["status"] == "EXPIRED"


@pytest.mark.django_db
@pytest.mark.parametrize("request_status", ["COMPLETED", "CANCELED"])
def test_closed_links_report_their_status(api_client, request_status):
    doc_request = DocumentRequestFactory(status=request_status)

    response = api_client.get(details_url(doc_request.token))

    assert response.data["status"] == request_status


@pytest.mark.django_db
def test_unknown_link_is_not_found(api_client):
    response = api_client.get(details_url(uuid.uuid4()))

    assert response.status_code == status.HTTP_404_NOT_FOUND
