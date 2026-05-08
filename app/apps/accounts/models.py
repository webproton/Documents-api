# app/apps/accounts/models.py

import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        if "is_active" not in extra_fields:
            user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()


class EmailConfirmation(models.Model):
    """
    Model for storing email confirmation tokens.

    Each record represents a unique confirmation link sent to the user.
    The token is used to verify user's email address within a limited time.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_confirmations",
        verbose_name="User",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Token",
        help_text="Unique token used for email confirmation",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created at",
        help_text="Time when confirmation token was created",
    )

    expires_at = models.DateTimeField(
        verbose_name="Expires at",
        help_text="Expiration time for the confirmation token",
    )

    is_confirmed = models.BooleanField(
        default=False,
        verbose_name="Is confirmed",
        help_text="Indicates whether the email has been confirmed",
    )

    @classmethod
    def create_email_confirmation(cls, user):
        """
        Create an email confirmation record for a given user.

        This function generates a unique UUID token and sets an expiration
        time (default: 24 hours from creation).

        Args:
            user (User): The user instance for whom the confirmation is created.

        Returns:
            EmailConfirmation: Created confirmation instance.
        """

        return cls.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(days=1),
            is_confirmed=False,
        )

    @classmethod
    def get_valid_email_confirmation(cls, token):
        """
        Retrieve active email confirmation by token.
        """

        # Try to find a valid confirmation:
        # - matches token
        # - not already confirmed
        # - not expired
        try:
            return cls.objects.get(
                token=token,
                is_confirmed=False,
                expires_at__gt=timezone.now(),
            )
        except cls.DoesNotExist:
            # If not found → return None instead of exception
            return None

    def confirm_email(self):
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

        # If user already active → nothing to do
        if self.user.is_active:
            return self
        # already used → no-op (idempotent safety)
        if self.is_confirmed:
            return self

        # activate user
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        # Mark current confirmation as used
        self.is_confirmed = True
        self.save(update_fields=["is_confirmed"])

        #  Invalidate all other confirmations for this user
        self.__class__.objects.filter(user=self.user, is_confirmed=False).update(
            is_confirmed=True
        )

        return self

    @classmethod
    def confirm_email_by_token(cls, token):
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
        confirmation = cls.objects.filter(
            token=token,
            expires_at__gt=timezone.now(),
        ).first()

        # If token not found or expired → stop flow
        if not confirmation:
            return None

        # Delegate full confirmation logic (activate user, mark used, etc.)
        return confirmation.confirm_email()

    def is_expired(self):
        """
        Check whether the confirmation token is expired.
        """
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"EmailConfirmation for {self.user.email}"
