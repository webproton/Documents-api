# app/apps/accounts/services.py
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import EmailConfirmation, User
from .tasks import send_confirmation_email_task


def send_confirmation_email(*, user, confirmation):
    """
    Dispatch async email sending task.
    """

    send_confirmation_email_task.delay(
        user_email=user.email,
        token=str(confirmation.token),  # if UUID ok or later its signed token - not ok
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

    # 3 already used → no-op (idempotent safety)
    if confirmation.is_confirmed:
        return confirmation

    # 4 activate user
    user.is_active = True
    user.save(update_fields=["is_active"])

    # 5 Mark current confirmation as used
    confirmation.is_confirmed = True
    confirmation.save(update_fields=["is_confirmed"])

    #  Invalidate all other confirmations for this user
    EmailConfirmation.objects.filter(user=user, is_confirmed=False).update(
        is_confirmed=True
    )

    return confirmation


def register_user_flow(*, email: str, password: str) -> User:
    user = User.objects.create_user(
        email=email,
        password=password,
        is_active=False,
    )

    register_user(user=user)

    return user


@transaction.atomic
def register_user(*, user: User) -> User:
    """
    - create email confirmation
    - send email
    """

    confirmation = create_email_confirmation(user)
    transaction.on_commit(
        lambda: send_confirmation_email_task.delay(
            user_email=user.email,
            token=str(confirmation.token),
        )
    )

    return user


def confirm_email_by_token(*, token):
    """
    Entry point for email confirmation flow.

    Responsibilities:
    - Retrieve EmailConfirmation by token
    - Ensure token is not expired
    - Delegate business logic to confirm_email()

    Returns:
        EmailConfirmation if successful
        None if token is invalid or expired
    """

    # Fetch confirmation by token with expiration check only
    confirmation = EmailConfirmation.objects.filter(
        token=token,
        expires_at__gt=timezone.now(),
    ).first()

    # If token not found or expired → stop flow
    if not confirmation:
        return None

    # Delegate full confirmation logic (activate user, mark used, etc.)
    return confirm_email(confirmation)
