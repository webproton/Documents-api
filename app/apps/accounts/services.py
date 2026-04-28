import os
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailConfirmation

EMAIL_CONFIRM_BASE_URL = os.getenv("EMAIL_CONFIRM_BASE_URL")


def send_confirmation_email(*, user, confirmation):
    """
    Send email confirmation link to user.
    """

    confirm_url = f"{settings.EMAIL_CONFIRM_BASE_URL}" f"?token={confirmation.token}"

    send_mail(
        subject="Confirm your email",
        message=f"Click the link to confirm your email:\n{confirm_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def create_email_confirmation(user):
    """
    Create an email confirmation record for a given user.

    This function generates a unique UUID token and sets an expiration
    time (default: 24 hours from creation).

    Args:
        user (User): The user instance for whom the confirmation is created.

    Returns:
        EmailConfirmation: Created confirmation instance.
    """

    confirmation = EmailConfirmation.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(days=1),
        is_confirmed=False,
    )

    # # 🔥 сразу отправляем письмо
    # send_confirmation_email(user, confirmation.token)

    return confirmation


def get_valid_email_confirmation(token):
    """
    Retrieve active email confirmation by token.
    """

    # Try to find a valid confirmation:
    # - matches token
    # - not already confirmed
    # - not expired
    try:
        return EmailConfirmation.objects.get(
            token=token,
            is_confirmed=False,
            expires_at__gt=timezone.now(),
        )
    except EmailConfirmation.DoesNotExist:
        # If not found → return None instead of exception
        return None


def confirm_email(confirmation):
    """
    Confirm user's email and activate account.

    Steps:
    - Check confirmation validity
    - Skip if already used or user is active
    - Mark confirmation as confirmed
    - Activate user
    - Invalidate other confirmation tokens

    Returns:
        EmailConfirmation or None
    """

    # 1. If confirmation invalid or expired → stop flow
    if not confirmation:
        return None

    user = confirmation.user

    # 2. If user already active → nothing to do
    if user.is_active:
        return confirmation

    # 3 Mark current confirmation as used
    confirmation.is_confirmed = True
    confirmation.save(update_fields=["is_confirmed"])

    # 4 Activate user account

    user.is_active = True
    user.save(update_fields=["is_active"])

    #  Invalidate all other confirmations for this user
    EmailConfirmation.objects.filter(user=user, is_confirmed=False).update(
        is_confirmed=True
    )

    return confirmation
