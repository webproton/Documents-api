# app/apps/documents/tests/test_document_limit_api.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.documents.models import Document, DocumentRequest
from app.apps.documents.tests.factories import (
    DocumentFactory,
    DocumentRequestFactory,
    DocumentTypeFactory,
)


def _set_plan(user, plan):
    Subscription.objects.filter(user=user).update(plan=plan)
    user.refresh_from_db()
    return user.subscription


@pytest.mark.django_db
def test_upload_blocked_when_limit_reached_new_folder(api_client, user):
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    DocumentFactory(
        user=user, document_type=DocumentTypeFactory(), status=Document.STATUS.ACTIVE
    )

    api_client.force_authenticate(user=user)
    new_type = DocumentTypeFactory()
    url = reverse("apps.documents:upload")

    payload = {
        "name": "Second Document",
        "document_type": new_type.id,
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        ),
    }
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "document_type" in response.data["errors"]


@pytest.mark.django_db
def test_upload_blocked_when_replacing_existing_folder_at_limit(api_client, user):
    """
    Replacing a document in an already-existing folder still counts
    against the total document count — it does NOT get a free pass,
    since the old (REPLACED) document still exists in the database.
    """
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    doc_type = DocumentTypeFactory()
    DocumentFactory(user=user, document_type=doc_type, status=Document.STATUS.ACTIVE)

    api_client.force_authenticate(user=user)
    url = reverse("apps.documents:upload")

    payload = {
        "name": "Updated Version",
        "document_type": doc_type.id,
        "file": SimpleUploadedFile(
            "v2.pdf", b"content", content_type="application/pdf"
        ),
    }
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "document_type" in response.data["errors"]


@pytest.mark.django_db
def test_upload_allowed_when_unlimited_plan(api_client, user):
    unlimited_plan = PlanFactory(name=Plan.NAME.BUSINESS)
    unlimited_plan.document_limit = None
    unlimited_plan.save(update_fields=["document_limit"])
    _set_plan(user, unlimited_plan)

    for _ in range(10):
        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )

    api_client.force_authenticate(user=user)
    url = reverse("apps.documents:upload")
    payload = {
        "name": "One More",
        "document_type": DocumentTypeFactory().id,
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        ),
    }
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_anonymous_upload_blocked_when_replacing_requester_folder_at_limit(
    api_client, user
):
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    doc_type = DocumentTypeFactory()
    DocumentFactory(user=user, document_type=doc_type, status=Document.STATUS.ACTIVE)

    doc_request = DocumentRequestFactory(
        requester=user, document_type=doc_type, status=DocumentRequest.STATUS.PENDING
    )

    url = reverse(
        "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
    )
    payload = {
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        )
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_upload_blocked_when_limit_reached(api_client, user):
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    DocumentFactory(
        user=user, document_type=DocumentTypeFactory(), status=Document.STATUS.ACTIVE
    )

    api_client.force_authenticate(user=user)
    new_type = DocumentTypeFactory()
    url = reverse("apps.documents:upload")

    payload = {
        "name": "Second Document",
        "document_type": new_type.id,
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        ),
    }
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "document_type" in response.data["errors"]


@pytest.mark.django_db
def test_upload_allowed_on_default_free_plan_below_limit(api_client, user):
    """Default FREE (limit=5) — normal upload passes."""
    api_client.force_authenticate(user=user)
    doc_type = DocumentTypeFactory()
    url = reverse("apps.documents:upload")

    payload = {
        "name": "First Document",
        "document_type": doc_type.id,
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        ),
    }
    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_anonymous_upload_blocked_when_requester_limit_reached(api_client, user):
    """
    The limit is also checked for the requester
    when uploading anonymously by token.
    """
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    DocumentFactory(
        user=user, document_type=DocumentTypeFactory(), status=Document.STATUS.ACTIVE
    )

    new_type = DocumentTypeFactory()
    doc_request = DocumentRequestFactory(
        requester=user, document_type=new_type, status=DocumentRequest.STATUS.PENDING
    )

    url = reverse(
        "apps.documents:anonymous-upload", kwargs={"token": doc_request.token}
    )
    payload = {
        "file": SimpleUploadedFile(
            "doc.pdf", b"content", content_type="application/pdf"
        )
    }

    response = api_client.post(url, data=payload, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "document_type" in response.data["errors"]

    # the request should not go to COMPLETED when the limit fails
    doc_request.refresh_from_db()
    assert doc_request.status == DocumentRequest.STATUS.PENDING
