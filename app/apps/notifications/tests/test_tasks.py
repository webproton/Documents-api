from unittest.mock import patch

import pytest
from django.core import mail

from app.apps.notifications.models import Notification
from app.apps.notifications.tasks import send_notification_email_task

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
    assert notification.user == user


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
