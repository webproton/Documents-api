# app/apps/accounts/services.py


from django.db import transaction

from .models import EmailConfirmation, User
from .tasks import send_confirmation_email_task


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

    confirmation = EmailConfirmation.create_email_confirmation(user)
    transaction.on_commit(
        lambda: send_confirmation_email_task.delay(
            user_email=user.email,
            token=str(confirmation.token),
        )
    )

    return user
