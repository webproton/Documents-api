from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app.apps.documents.models import Document
from app.apps.documents.tasks import send_document_request_email_task
from app.apps.documents.tests.factories import (
    DocumentFactory,
    DocumentRequestFactory,
    DocumentTypeFactory,
)


@pytest.mark.django_db
class TestDocumentRequestNotifications:
    """We isolate the tests from the real Celery.
    The tests won't attempt to start a broker or send a real email;
    they simply verify that the .delay() method was called with the correct ID.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self, api_client, user):
        self.client = api_client
        self.user = user
        self.client.force_authenticate(user=self.user)
        self.document_type = DocumentTypeFactory()

    @pytest.mark.django_db(transaction=True)
    def test_create_document_request_triggers_celery(self):
        """
        We're verifying that when a request is successfully created via the API,
        the Celery background task is automatically called.
        """
        url = reverse("apps.documents:document-request-list")
        data = {
            "recipient_email": "test_recipient@example.com",
            "document_type": self.document_type.id,
        }

        with patch.object(send_document_request_email_task, "delay") as mock_delay:
            response = self.client.post(url, data=data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        # We check that the Celery task was called exactly once.
        mock_delay.assert_called_once()

        # We check that the ID of the created request was passed to the task.
        created_request_id = response.data["id"]
        mock_delay.assert_called_with(created_request_id)

    def test_cancel_document_request_success(self):
        """
        An authorized user can successfully cancel their PENDING request.
        The status should change to CANCELED.
        """
        doc_request = DocumentRequestFactory(
            requester=self.user, document_type=self.document_type, status="PENDING"
        )
        # DRF Router /api/documents/requests/{id}/cancel/
        url = reverse(
            "apps.documents:document-request-cancel", kwargs={"pk": doc_request.id}
        )

        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Document request has been canceled."

        # Checking changes in the database
        doc_request.refresh_from_db()
        assert doc_request.status == "CANCELED"

    def test_cannot_cancel_already_completed_request(self):
        """
        You cannot cancel a request that is already in the COMPLETED status.
        """
        doc_request = DocumentRequestFactory(
            requester=self.user, document_type=self.document_type, status="COMPLETED"
        )
        url = reverse(
            "apps.documents:document-request-cancel", kwargs={"pk": doc_request.id}
        )

        response = self.client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot cancel a request" in response.data["errors"]["detail"]

    @patch.object(send_document_request_email_task, "delay")
    def test_resend_notification_success_after_one_hour(self, mock_celery_task):
        """
        A resend is successful if more than 1 hour has passed since the last send.
        The last_sent_at time is updated.
        """
        # We simulate that the email was sent 2 hours ago.
        two_hours_ago = timezone.now() - timedelta(hours=2)
        doc_request = DocumentRequestFactory(
            requester=self.user,
            document_type=self.document_type,
            status="PENDING",
            last_sent_at=two_hours_ago,
        )
        url = reverse(
            "apps.documents:document-request-resend", kwargs={"pk": doc_request.id}
        )

        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Notification resent successfully."

        # checking Celery to resend.
        mock_celery_task.assert_called_once_with(doc_request.id)

        # check that the sending time has been updated to the current one
        doc_request.refresh_from_db()
        assert doc_request.last_sent_at > two_hours_ago

    def test_resend_notification_rate_limited_within_one_hour(self):
        """
        Rate limit: If a repeat request is sent within 1 hour of the previous one,
        the API returns a 400 error.
        """
        # We'll simulate the email being sent just 30 minutes ago.
        thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
        doc_request = DocumentRequestFactory(
            requester=self.user,
            document_type=self.document_type,
            status="PENDING",
            last_sent_at=thirty_minutes_ago,
        )
        url = reverse(
            "apps.documents:document-request-resend", kwargs={"pk": doc_request.id}
        )

        response = self.client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "You can resend notification once per hour"
            in response.data["errors"]["detail"]
        )

    def test_expire_prolonged_requests_cron_logic(self):
        """
        We're verifying that the mass close method correctly sets
        requests with expired expires_at to EXPIRED status,
        leaving existing requests untouched.
        """
        # Create an expired query (expires_at in the past)
        expired_deadline = timezone.now() - timedelta(days=1)
        expired_request = DocumentRequestFactory(
            document_type=self.document_type,
            status="PENDING",
            expires_at=expired_deadline,
        )

        # Create an active query (expires_at in the future)
        active_deadline = timezone.now() + timedelta(days=29)
        active_request = DocumentRequestFactory(
            document_type=self.document_type,
            status="PENDING",
            expires_at=active_deadline,
        )

        # call the service method (which will trigger Celery Beat)
        from app.apps.documents.tasks import auto_expire_document_requests_task

        result_message = auto_expire_document_requests_task()

        # check that exactly 1 record has been updated
        assert result_message == "Successfully expired 1 document requests."

        # Checking changes in the database
        expired_request.refresh_from_db()
        active_request.refresh_from_db()

        assert expired_request.status == "EXPIRED"
        assert active_request.status == "PENDING"  # The fresh request has not changed

    def test_delete_replaced_document_does_not_affect_others(self):
        """If a REPLACED document is deleted, it simply disappears."""
        active_doc = DocumentFactory(
            user=self.user, document_type=self.document_type, status="ACTIVE"
        )
        replaced_doc = DocumentFactory(
            user=self.user, document_type=self.document_type, status="REPLACED"
        )
        # call the model's .delete() method
        replaced_doc.delete()

        # We check that the active one remains in place
        # and the old one has been deleted.
        active_doc.refresh_from_db()
        assert active_doc.status == "ACTIVE"
        assert not Document.objects.filter(id=replaced_doc.id).exists()

    def test_delete_active_document_restores_previous_replaced(self):
        """If ACTIVE is deleted the last REPLACED becomes ACTIVE"""
        # We create a chain from old to new
        oldest_replaced = DocumentFactory(
            user=self.user, document_type=self.document_type, status="REPLACED"
        )
        latest_replaced = DocumentFactory(
            user=self.user, document_type=self.document_type, status="REPLACED"
        )
        active_doc = DocumentFactory(
            user=self.user, document_type=self.document_type, status="ACTIVE"
        )

        # Deleting the active document
        active_doc.delete()

        # Check that active_doc has been deleted
        assert not Document.objects.filter(id=active_doc.id).exists()

        # check that the most recent REPLACED has become ACTIVE
        latest_replaced.refresh_from_db()
        assert latest_replaced.status == "ACTIVE"

        # check that the very old one is still REPLACED
        oldest_replaced.refresh_from_db()
        assert oldest_replaced.status == "REPLACED"
