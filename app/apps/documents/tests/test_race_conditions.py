import concurrent.futures

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.documents.models import Document
from app.apps.documents.serializers.document import DocumentUploadSerializer
from app.apps.documents.tests.factories import DocumentTypeFactory


def _set_plan(user, plan):
    Subscription.objects.filter(user=user).update(plan=plan)
    user.refresh_from_db()
    return user.subscription


def _make_concurrent_uploads(user, url, doc_type_id, max_workers=2):
    """
    Helper function: closes stale connections and executes
    requests concurrently in multiple threads.
    """

    def _upload():
        # Close connection for the new thread
        connection.close()

        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)

        payload = {
            "name": "Parallel Document",
            "document_type": doc_type_id,
            "file": SimpleUploadedFile(
                "doc.pdf", b"content", content_type="application/pdf"
            ),
        }
        response = client.post(url, data=payload, format="multipart")
        # Explicitly close thread connection before exit
        connection.close()
        return response

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_upload) for _ in range(max_workers)]
        done, _ = concurrent.futures.wait(futures)
        results = [f.result() for f in done]

    return results


# =====================================================================
# TEST 1: Vulnerable code simulation (Limit check only in validate())
# =====================================================================
@pytest.mark.django_db(transaction=True)
def test_race_condition_bypasses_limit_when_validated_in_validate_only(
    user, monkeypatch
):
    """
    DEMONSTRATES PROTECTION FAILURE:
    If we check the limit in validate(), 2 concurrent requests
    pass validate() BEFORE the first one manages to write the file to the DB.
    As a result, 2 documents are created when the limit = 1.
    """
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    url = reverse("apps.documents:upload")
    doc_type = DocumentTypeFactory()

    # Unsafe create simulating old behavior without locks
    def unsafe_create(serializer_instance, validated_data):
        name = validated_data.get("name") or validated_data["file"].name
        return Document.objects.create(
            user=user,
            name=name,
            file=validated_data["file"],
            document_type=validated_data["document_type"],
            status=Document.STATUS.ACTIVE,
        )

    monkeypatch.setattr(DocumentUploadSerializer, "create", unsafe_create)

    results = _make_concurrent_uploads(user, url, doc_type.id, max_workers=2)

    status_codes = [r.status_code for r in results]
    assert status_codes == [status.HTTP_201_CREATED, status.HTTP_201_CREATED]

    total_docs = Document.objects.filter(user=user).count()
    assert total_docs == 2


# =====================================================================
# TEST 2: Secure code (Limit check under select_for_update() in create())
# =====================================================================
@pytest.mark.django_db(transaction=True)
def test_race_condition_prevented_when_checked_under_lock_in_create(user):
    """
    DEMONSTRATES WORKING PROTECTION:
    Thanks to User.objects.select_for_update() in create(), the second thread
    waits for the first thread to finish, recounts documents, and blocks the breach.
    """
    limited_plan = PlanFactory(name=Plan.NAME.PRO)
    limited_plan.document_limit = 1
    limited_plan.save(update_fields=["document_limit"])
    _set_plan(user, limited_plan)

    url = reverse("apps.documents:upload")
    doc_type = DocumentTypeFactory()

    results = _make_concurrent_uploads(user, url, doc_type.id, max_workers=2)

    status_codes = [r.status_code for r in results]

    assert status.HTTP_201_CREATED in status_codes
    assert status.HTTP_400_BAD_REQUEST in status_codes

    total_docs = Document.objects.filter(user=user).count()
    assert total_docs == 1
