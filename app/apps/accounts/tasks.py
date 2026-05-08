# apps/accounts/tasks.py

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_confirmation_email_task(*, user_email: str, token: str):
    """
    Async email sending task.

    Runs outside request cycle.
    """

    confirm_url = f"{settings.EMAIL_CONFIRM_BASE_URL}?token={token}"

    send_mail(
        subject="Confirm your email",
        message=f"Click the link to confirm your email:\n{confirm_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        fail_silently=False,
    )
