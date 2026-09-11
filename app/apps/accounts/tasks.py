# apps/accounts/tasks.py
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .utils import SMSService

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
)
def send_sms_task(self, phone_number: str, code: str) -> bool:
    """
    Celery task for sending SMS OTP codes via SMSService.
    Automatically retries up to 3 times on unexpected exceptions.
    """
    logger.info(f"Dispatched send_sms_task for phone: {phone_number}")
    success = SMSService.send_otp(phone_number, code)
    if not success:
        logger.warning(f"SMSService failed to send SMS to {phone_number}")
    return success


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
)
def send_email_otp_task(self, user_id: int, code: str) -> bool:
    """
    Celery task for sending 2FA OTP codes via Email.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"send_email_otp_task failed: User ID {user_id} does not exist.")
        return False

    subject = render_to_string("accounts/emails/otp_email_subject.txt").strip()
    minutes = getattr(settings, "PRE_AUTH_TOKEN_LIFETIME", 1200) // 60
    message = render_to_string(
        "accounts/emails/otp_email.txt",
        {
            "code": code,
            "minutes": minutes,
        },
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Successfully sent 2FA email OTP to user ID: {user_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send 2FA email OTP to user ID {user_id}: {exc}")
        raise exc
