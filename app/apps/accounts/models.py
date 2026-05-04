# app/apps/accounts/models.py

import uuid

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

    def is_expired(self):
        """
        Check whether the confirmation token is expired.
        """
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"EmailConfirmation for {self.user.email}"
