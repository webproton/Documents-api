import pytest
from apps.accounts.tests.factories import UserFactory
from django.core import mail

from app.apps.accounts.tasks import send_email_otp_task


@pytest.mark.django_db
def test_send_email_otp_task_builds_and_sends_email():
    """
    Render the real OTP templates (other tests mock this task):
    the subject must be a single line, otherwise Django refuses to send it.
    """
    user = UserFactory()

    result = send_email_otp_task.apply(args=[user.id, "123456"]).get()

    assert result is True
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [user.email]
    assert email.subject == "Your Two-Factor Authentication Verification Code"
    assert "Your verification code is: 123456" in email.body
    assert "This code is valid for 20 minutes." in email.body
    assert not email.body.startswith("#")
