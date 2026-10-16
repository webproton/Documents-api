# app/apps/accounts/models.py

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models, transaction
from django.utils import timezone
from model_utils import Choices
from model_utils.models import TimeStampedModel

from .querysets import UserDeviceQuerySet
from .utils import (
    extract_raw_device_token,
    generate_otp_code,
    get_client_ip,
    get_geoip_location,
    hash_otp_code,
)


class UserDevice(TimeStampedModel):
    """
    A browser/device the user is signed in from (one row per device token).

    Every login creates or refreshes a row, so the user sees all active
    sessions. Two separate deadlines:
    - expires_at: the session is alive until then (refresh token lifetime,
      extended on every token refresh; set to now on logout). JWTs carry
      the row id in the "device_id" claim and stop working once the session
      is revoked or expired.
    - trusted_until: 2FA is skipped on this device until then (90 days after
      a successful 2FA with "remember device"). Null = not trusted.

    Inherits 'created' and 'modified' timestamps from TimeStampedModel.
    Stores a SHA-256 hash of the client token sent back via cookies/headers.
    """

    objects = UserDeviceQuerySet.as_manager()

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="devices",
        verbose_name="User",
        help_text="User owning this trusted device",
    )
    is_revoked = models.BooleanField(default=False)

    device_token_hash = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Device token hash",
        help_text="SHA-256 hash of the unique device identification token",
    )

    user_agent = models.CharField(
        max_length=512,
        blank=True,
        verbose_name="User agent",
        help_text="User-Agent browser string associated with the device",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP address",
        help_text="Last recorded IP address of the device",
    )

    expires_at = models.DateTimeField(
        verbose_name="Expires at",
        help_text="Session stays active until then; extended on token refresh",
    )

    trusted_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Trusted until",
        help_text="2FA is skipped on this device until then (null = not trusted)",
    )

    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last login at",
        help_text="Timestamp of the last successful authentication from this device",
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Location",
        help_text="City and country resolved from IP address",
    )

    class Meta:
        verbose_name = "User device"
        verbose_name_plural = "User devices"
        ordering = ["-last_login_at"]

    @staticmethod
    def hash_token(token: str) -> str:
        """Calculate SHA-256 hash for raw device token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_trusted(self) -> bool:
        """Whether 2FA can be skipped on this device right now."""
        return (
            not self.is_revoked
            and self.trusted_until is not None
            and self.trusted_until > timezone.now()
        )

    @staticmethod
    def session_lifetime() -> timedelta:
        """A session lives as long as its refresh token."""
        return settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    def __str__(self) -> str:
        return f"Device {self.device_token_hash[:8]} for {self.user.email}"

    def touch(self) -> None:
        """Call this when the device is
        actually used to skip 2FA — not on every save()."""
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at"])

    def revoke(self) -> None:
        """End the session and drop the trusted status (user action).
        JWTs with this device_id are rejected from now on."""
        self.is_revoked = True
        self.trusted_until = None
        self.save(update_fields=["is_revoked", "trusted_until"])

    def end_session(self) -> None:
        """Logout: the session ends now; a trusted device stays trusted
        until its 90 days run out (spec: logout keeps the trusted device)."""
        self.expires_at = timezone.now()
        self.save(update_fields=["expires_at"])

    def extend_session(self) -> None:
        """Token refresh: keep an actively used session alive."""
        session_end = timezone.now() + self.session_lifetime()
        if session_end > self.expires_at:
            self.expires_at = session_end
            self.save(update_fields=["expires_at"])

    @classmethod
    def issue(cls, user, request, *, trusted=False) -> tuple["UserDevice", str]:
        """
        Start a session for this browser on login and rotate its device token.

        Reuses the row matching the device token sent with the request
        (also a revoked one — the user just authenticated again), otherwise
        creates a new row.

        trusted=True (2FA passed with "remember device") trusts the device
        for TRUSTED_DEVICE_LIFETIME_DAYS. Otherwise an existing trust is kept,
        but a revoked device never keeps it.
        """
        now = timezone.now()
        raw_token = secrets.token_urlsafe(32)
        ip_address = get_client_ip(request) if request else None

        device = None
        existing_raw_token = extract_raw_device_token(request) if request else None
        if existing_raw_token:
            device = cls.objects.filter(
                user=user,
                device_token_hash=cls.hash_token(existing_raw_token),
            ).first()
        if device is None:
            device = cls(user=user)

        if trusted:
            device.trusted_until = now + timedelta(
                days=settings.TRUSTED_DEVICE_LIFETIME_DAYS
            )
        elif device.is_revoked:
            device.trusted_until = None

        device.device_token_hash = cls.hash_token(raw_token)
        device.is_revoked = False
        device.last_login_at = now
        device.ip_address = ip_address
        device.user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""
        device.location = get_geoip_location(ip_address) if ip_address else ""
        device.expires_at = now + cls.session_lifetime()
        device.save()
        return device, raw_token


def avatar_upload_path(instance, filename):
    ext = filename.split(".")[-1]
    return f"users/{instance.id}/avatar/{uuid.uuid4()}.{ext}"


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

    REGISTRATION_METHOD = Choices(
        ("EMAIL", "Email"),
        ("GOOGLE", "Google"),
    )

    TWO_FACTOR_METHOD = Choices(
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
    )

    is_blocked = models.BooleanField(default=False)

    registration_method = models.CharField(
        max_length=20,
        choices=REGISTRATION_METHOD,
        default=REGISTRATION_METHOD.EMAIL,
    )

    username = None
    email = models.EmailField(unique=True)

    avatar = models.ImageField(blank=True, null=True, upload_to=avatar_upload_path)

    is_2fa_enabled = models.BooleanField(
        default=False,
        verbose_name="Is 2FA enabled",
        help_text="Designates whether two-factor"
        "authentication is enabled for this user",
    )

    two_factor_method = models.CharField(
        max_length=20,
        choices=TWO_FACTOR_METHOD,
        default=TWO_FACTOR_METHOD.EMAIL,
        verbose_name="2FA Method",
        help_text="Primary two-factor authentication channel",
    )

    phone_number = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Phone number",
        help_text="Phone number for SMS-based 2FA",
    )

    phone_confirmed = models.BooleanField(
        default=False,
        verbose_name="Phone confirmed",
        help_text="Whether phone_number has been verified via SMS code",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()


class SocialAccount(models.Model):
    """Store a social account linked to a user."""

    PROVIDER = Choices(
        ("GOOGLE", "Google"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER,
    )
    provider_user_id = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="unique_social_account",
            ),
        ]

    def __str__(self):
        return f"{self.provider}: {self.user.email}"


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

    @transaction.atomic
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

        # # If user already active → nothing to do
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
            is_confirmed=False,
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


class PhoneConfirmation(TimeStampedModel):
    """
    Model for confirming a user's phone number before it can be used
    for SMS-based 2FA. Mirrors EmailConfirmation, but the code is
    delivered via SMS and stored as a hash, not a plain UUID link.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="phone_confirmations",
        verbose_name="User",
    )

    phone_number = models.CharField(
        max_length=32,
        verbose_name="Phone number",
        help_text="The phone number this confirmation attempt is for",
    )

    code_hash = models.CharField(max_length=64)

    expires_at = models.DateTimeField(
        verbose_name="Expires at",
        help_text="Expiration time for the confirmation code",
    )

    is_confirmed = models.BooleanField(default=False)

    CODE_TTL_MINUTES = 20

    @classmethod
    def create_for_phone(
        cls, user, phone_number: str
    ) -> tuple["PhoneConfirmation", str]:
        """Create a new confirmation attempt;
        returns (instance, raw_code) to send via SMS."""
        raw_code = generate_otp_code()

        instance = cls.objects.create(
            user=user,
            phone_number=phone_number,
            code_hash=hash_otp_code(raw_code),
            expires_at=timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES),
        )
        return instance, raw_code

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @transaction.atomic
    def confirm(self, raw_code: str) -> bool:
        """Verify raw_code; on success mark confirmed and set user.phone_confirmed."""
        if self.is_confirmed or self.is_expired():
            return False

        if not hmac.compare_digest(hash_otp_code(raw_code), self.code_hash):
            return False

        self.is_confirmed = True
        self.save(update_fields=["is_confirmed"])

        self.user.phone_number = self.phone_number
        self.user.phone_confirmed = True
        self.user.save(update_fields=["phone_number", "phone_confirmed"])

        return True

    def __str__(self) -> str:
        return f"PhoneConfirmation for {self.user.email} ({self.phone_number})"
