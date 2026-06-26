from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from app.apps.documents.tests.factories import DocumentFactory
from app.apps.notifications.models import Notification
from app.apps.notifications.tasks import (
    check_document_expirations_cron_task,
    send_notification_email_task,
)

pytestmark = pytest.mark.django_db


def test_send_email_confirmation_task_success(user):
    """
    Verify successful notification task execution:
    HTML email delivery and database logging.
    """
    # --- 1. ARRANGE (Setup Data) ---
    user.username = "Test"
    user.save()

    context = {"username": user.username, "confirmation_url": "http://test.com/confirm"}
    title = "Registration confirmation"

    # --- 2. ACT (Execute Task) ---
    send_notification_email_task(
        recipient_email=user.email,
        context=context,
        notification_code=Notification.TYPE.EMAIL_CONFIRMATION,
        title=title,
        user_id=user.id,
    )

    # --- 3. ASSERT (Verify Email Delivery) ---
    assert len(mail.outbox) == 1
    email = mail.outbox[0]

    assert email.subject == title
    assert user.email in email.to

    # Safely extract HTML content without relying on hardcoded indexes [0]
    html_body = next(
        (content for content, mime in email.alternatives if mime == "text/html"), None
    )
    assert html_body is not None, "HTML body not found in email alternatives"

    # Verify dynamic context rendering inside the HTML template
    assert "Hello dear" in html_body
    assert user.username in html_body
    assert context["confirmation_url"] in html_body

    # --- 4. ASSERT (Verify Database Log) ---
    notification = Notification.objects.get(recipient_email=user.email)
    assert notification.status == Notification.STATUS.SENT
    assert notification.type == Notification.TYPE.EMAIL_CONFIRMATION
    assert notification.sent_at is not None


def test_send_email_confirmation_task_failure(user):
    """
    Verify notification task behavior during SMTP
    server failure: database log status is set to FAILED.
    """
    # --- 1. ARRANGE (Setup Data) ---
    context = {"username": user.username}
    title = "Registration Failure Test"

    # --- 2. ACT (Execute Task with Mocked Exception) ---
    # Simulate an SMTP server crash by mocking Django's send_mail function
    with patch(
        "app.apps.notifications.tasks.send_mail",
        side_effect=Exception("SMTP Connection Error"),
    ):
        send_notification_email_task(
            recipient_email=user.email,
            context=context,
            notification_code=Notification.TYPE.EMAIL_CONFIRMATION,
            title=title,
            user_id=user.id,
        )

    # --- 3. ASSERT (Verify No Email Sent & Database Log Status) ---
    # Ensure that no email was actually dispatched to the outbox
    assert len(mail.outbox) == 0

    # Verify that the database record correctly
    # caught the exception and logged FAILED status
    notification = Notification.objects.get(recipient_email=user.email)
    assert notification.status == Notification.STATUS.FAILED
    assert notification.type == Notification.TYPE.EMAIL_CONFIRMATION
    assert notification.sent_at is None


@patch("app.apps.notifications.tasks.send_notification_email_task.delay")
def test_check_document_expirations_cron_task_success(mock_send_email, user):
    """
    Verify that the cron task triggers an email notification
    for active documents expiring within 30 days.
    """

    mock_send_email.side_effect = send_notification_email_task
    # ARRANGE (Setup Data)
    today = timezone.now().date()
    # Create an active document that expires in 30 days.
    expiring_doc = DocumentFactory(
        user=user, expiration_date=today + timedelta(days=30), is_reminder_sent=False
    )

    # Execute Cron Task
    check_document_expirations_cron_task()

    # check that the asynchronous dispatch task was called exactly once.

    assert mock_send_email.call_count == 1
    # check :  field mark True
    expiring_doc.refresh_from_db()
    assert expiring_doc.is_reminder_sent is True

    # check that a REMINDER type record has been logged in the database.
    notification = Notification.objects.get(document=expiring_doc)
    assert notification.type == Notification.TYPE.REMINDER
    assert notification.user == user


@patch("app.apps.notifications.tasks.send_notification_email_task.delay")
def test_check_document_expirations_cron_task_excludes_inactive(mock_send_email, user):
    """
    Verify that the cron task ignores documents that are
    not 'active' (e.g., replaced), even if they expire within 30 days.
    """

    today = timezone.now().date()

    # factory status to REPLACED
    DocumentFactory(
        user=user,
        status="REPLACED",
        expiration_date=today + timedelta(days=15),
        is_reminder_sent=False,
    )

    # Execute Cron Task
    check_document_expirations_cron_task()

    assert mock_send_email.call_count == 0
    assert not Notification.objects.filter(type=Notification.TYPE.REMINDER).exists()


@patch("app.apps.notifications.tasks.send_notification_email_task.delay")
def test_check_document_expirations_cron_task_deduplication(mock_send_email, user):
    """
    Verify protection against duplicate notifications: if a REMINDER
    already exists for the document, no second email should be triggered.
    """

    mock_send_email.side_effect = send_notification_email_task
    today = timezone.now().date()

    doc = DocumentFactory(
        user=user, expiration_date=today + timedelta(days=10), is_reminder_sent=False
    )
    # Run the task for the first time to create a history entry.
    check_document_expirations_cron_task()
    assert mock_send_email.call_count == 1
    assert Notification.objects.filter(
        document=doc, type=Notification.TYPE.REMINDER
    ).exists()

    # Reset the mock counter before the second launch
    mock_send_email.reset_mock()

    # Execute Cron Task a Second Time
    check_document_expirations_cron_task()
    # The call counter should remain zero,
    # since the duplicate protection has been triggered.
    assert mock_send_email.call_count == 0
