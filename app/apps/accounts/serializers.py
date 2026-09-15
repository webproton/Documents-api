import re

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenObtainSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

from app.apps.notifications.tasks import send_notification_email_task

from .models import (
    EmailConfirmation,
    PhoneConfirmation,
    SocialAccount,
    User,
    UserDevice,
)
from .redis_manager import TwoFactorRedisManager
from .tasks import send_email_otp_task, send_sms_task


class TwoFactorVerifySerializer(serializers.Serializer):
    """
    Serializer to verify 2FA OTP code using pre_auth_token during login.
    """

    pre_auth_token = serializers.UUIDField(
        required=True,
        help_text="Pre-authorization token received from initial login step.",
    )
    code = serializers.CharField(
        required=True,
        max_length=6,
        min_length=6,
        help_text="6-digit OTP code sent via SMS or Email.",
    )

    def validate_code(self, value):
        if not re.match(r"^\d{6}$", value):
            raise serializers.ValidationError(
                "OTP code must consist of exactly 6 digits."
            )
        return value

    def validate(self, attrs):
        """Verify the OTP against Redis and resolve the target user."""
        is_valid, user_id, error_message = TwoFactorRedisManager.verify_otp_code(
            pre_auth_token=str(attrs["pre_auth_token"]),
            input_code=attrs["code"],
        )

        if not is_valid:
            raise serializers.ValidationError(
                error_message or "Invalid or expired OTP code."
            )

        user = User.objects.filter(id=user_id).first()
        if user is None:
            raise serializers.ValidationError("User not found.")

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        """Issue JWT tokens for the verified user."""
        user = self.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class RequestPhoneConfirmationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=32)

    def validate_phone_number(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Phone number is required.")

        # Checking the E.164 format (+ and 9 to 15 digits)
        if not re.match(r"^\+\d{9,15}$", value):
            raise serializers.ValidationError(
                "Phone number must be in international format (e.g. +1234567890)."
            )

        user = self.context["request"].user
        if User.objects.filter(phone_number=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "This phone number is already registered to another account."
            )

        return value

    @transaction.atomic
    def save(self, **kwargs) -> dict:
        """
        Invalidates old codes, creates a new
        confirmation record, and dispatches SMS.
        """
        user = self.context["request"].user
        phone_number = self.validated_data["phone_number"]

        # Block and delete inactive attempts
        PhoneConfirmation.objects.select_for_update().filter(
            user=user, is_confirmed=False
        ).delete()

        confirmation, code = PhoneConfirmation.create_for_phone(
            user=user, phone_number=phone_number
        )

        # send SMS only after a successful transaction commit
        transaction.on_commit(lambda: send_sms_task.delay(phone_number, code))

        return {"message": "Confirmation code sent."}


class ConfirmPhoneSerializer(serializers.Serializer):
    """Verify the SMS code sent to confirm a phone number."""

    code = serializers.CharField(max_length=6, min_length=6, required=True)

    def validate(self, attrs):
        user = self.context["request"].user

        confirmation = (
            PhoneConfirmation.objects.filter(user=user, is_confirmed=False)
            .order_by("-created")
            .first()
        )

        if not confirmation:
            raise serializers.ValidationError("Invalid or expired code.")

        attrs["confirmation"] = confirmation
        return attrs

    @transaction.atomic
    def confirm_phone(self) -> dict:
        """Verifies the code and confirms the phone record."""
        confirmation = self.validated_data["confirmation"]
        code = self.validated_data["code"]

        if not confirmation.confirm(code):
            raise serializers.ValidationError("Invalid or expired code.")

        return {"message": "Phone number confirmed."}


class Toggle2FASerializer(serializers.Serializer):
    """Serializer for enabling or disabling 2FA in user profile."""

    enable = serializers.BooleanField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    method = serializers.ChoiceField(
        choices=User.TWO_FACTOR_METHOD,
        default=User.TWO_FACTOR_METHOD.EMAIL,
        required=False,
    )

    def validate_password(self, value):
        """Verify user's current password before changing security settings."""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value

    def validate(self, attrs):
        """SMS 2FA can only be enabled if the phone number is already confirmed."""
        user = self.context["request"].user
        enable = attrs.get("enable")
        method = attrs.get("method", User.TWO_FACTOR_METHOD.EMAIL)

        if enable and method == User.TWO_FACTOR_METHOD.SMS:
            if not getattr(user, "phone_number", None) or not user.phone_confirmed:
                raise serializers.ValidationError(
                    {"method": "Confirm your phone number before enabling SMS 2FA."}
                )

        return attrs

    def toggle_2fa(self) -> dict:
        """Updates user's 2FA settings and returns a status response."""
        user = self.context["request"].user
        enable = self.validated_data["enable"]
        method = self.validated_data.get("method", User.TWO_FACTOR_METHOD.EMAIL)

        user.is_2fa_enabled = enable

        if enable:
            user.two_factor_method = method

        user.save(update_fields=["is_2fa_enabled", "two_factor_method"])

        status_str = "enabled" if enable else "disabled"
        return {
            "message": f"Two-factor authentication has been successfully {status_str}."
        }


class SafeTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Extends the standard refresh serializer to also reject blocked or
    inactive users. The default refresh flow only validates the
    token's signature and expiry, not the user's current state — so
    a blocked user could otherwise keep refreshing indefinitely with
    an old refresh token.
    """

    def validate(self, attrs):

        refresh_token = RefreshToken(attrs["refresh"])
        user_id = refresh_token.get("user_id")

        user = User.objects.filter(id=user_id).first()

        if not user or not user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        if user.is_blocked:
            raise AuthenticationFailed("This account has been blocked.")

        return super().validate(attrs)


class LogoutSerializer(serializers.Serializer):
    """Serializer for refresh token logout."""

    refresh = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    """Serializer for email-based JWT authentication."""

    username_field = "email"

    def validate(self, attrs):
        """Validate credentials and return JWT tokens with user data."""

        email = attrs.get("email")
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        # Check inactive (unconfirmed email) accounts before delegating
        # to the parent — Django's ModelBackend would otherwise reject
        # them with a generic "no active account" message that hides
        # the real reason.
        if user is not None and not user.is_active:
            raise AuthenticationFailed(
                "No active account found with the given credentials"
            )

        if user is not None and user.is_blocked:
            raise AuthenticationFailed("This account has been blocked.")

        # Verify the login/password WITHOUT calling TokenObtainPairSerializer.validate() —
        # he also mints tokens, and this cannot be done until the 2FA decision.
        # TokenObtainSerializer.validate() – up by MRO – only
        # authenticates and sets self.user.
        TokenObtainSerializer.validate(self, attrs)

        device = self._get_trusted_device()

        requires_2fa = self.user.is_2fa_enabled and device is None

        if requires_2fa:
            pre_auth_token, otp_code = TwoFactorRedisManager.create_2fa_session(
                user_id=self.user.id,
                method=self.user.two_factor_method,
            )
            # Sending OTP via Celery (separately SMS / Email)
            if self.user.two_factor_method == User.TWO_FACTOR_METHOD.SMS and getattr(
                self.user, "phone_number", None
            ):

                transaction.on_commit(
                    lambda: send_sms_task.delay(self.user.phone_number, otp_code)
                )
                message = "Verification code has been sent to your phone."
            else:
                transaction.on_commit(
                    lambda: send_email_otp_task.delay(self.user.id, otp_code)
                )
                message = "Verification code has been sent to your email."

            return {
                "requires_2fa": True,
                "pre_auth_token": pre_auth_token,
                "delivery_method": self.user.two_factor_method,
                "message": message,
            }

        if device is not None:
            device.touch()

        # 2FA is not needed (disabled or the device is trusted) – mint tokens now.
        refresh = self.get_token(self.user)

        # Explicitly update the last_login because we overridden validate()
        update_last_login(None, self.user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "email": self.user.email,
            "id": self.user.id,
            "requires_2fa": False,
        }

    def _get_trusted_device(self):
        """Return the matching non-revoked, non-expired UserDevice for the
        incoming device token header, or None."""

        request = self.context.get("request")
        if not request:
            return None

        raw_token = request.META.get("HTTP_X_DEVICE_TOKEN") or request.META.get(
            "X-Device-Token"
        )

        if not raw_token:
            return None

        return UserDevice.objects.filter(
            user=self.user,
            device_token_hash=UserDevice.hash_token(raw_token),
            is_revoked=False,
            expires_at__gt=timezone.now(),
        ).first()


class Resend2FASerializer(serializers.Serializer):
    """Serializer for requesting a new 2FA OTP code."""

    pre_auth_token = serializers.UUIDField(required=True)

    def validate(self, attrs):
        pre_auth_token = str(attrs["pre_auth_token"])

        # Reviewing and regenerating code in Redis
        success, new_otp, user_id, method, error_message = (
            TwoFactorRedisManager.resend_2fa_code(pre_auth_token)
        )

        if not success:
            raise ValidationError(error_message or "Invalid or expired session.")

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user or user.is_blocked:
            raise ValidationError("User not found or account is blocked.")

        attrs["user"] = user
        attrs["new_otp"] = new_otp
        attrs["method"] = method
        return attrs

    def resend_code(self) -> dict:
        """Dispatches OTP task via appropriate channel."""
        user = self.validated_data["user"]
        new_otp = self.validated_data["new_otp"]
        method = self.validated_data["method"]

        if method == User.TWO_FACTOR_METHOD.SMS and getattr(user, "phone_number", None):
            send_sms_task.delay(user.phone_number, new_otp)
            message = "A new verification code has been sent to your phone."
        else:
            send_email_otp_task.delay(user.id, new_otp)
            message = "A new verification code has been sent to your email."

        return {"message": message}


class UserSerializer(serializers.ModelSerializer):
    """Serializer for basic user data."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration and email confirmation setup."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    def validate_password(self, value):
        """Validate password against Django password rules."""

        validate_password(value)  # Django rules
        return value

    def validate_email(self, value):
        """Normalize and validate user email."""

        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")

        return value

    def validate(self, attrs):
        """Validate registration data."""

        if attrs["email"] in attrs["password"]:
            raise serializers.ValidationError("Password too similar to email")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create inactive user and send email confirmation."""

        try:
            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                is_active=False,
            )

            # Create a confirmation token
            confirmation = EmailConfirmation.create_email_confirmation(user)
            confirm_url = (
                f"{settings.EMAIL_CONFIRM_BASE_URL}?token={confirmation.token}"
            )

            # context mail
            email_context = {
                "username": user.email,
                "token": str(confirmation.token),
                "confirmation_url": confirm_url,
            }
            # to Celery only AFTER a successful commit to the database
            transaction.on_commit(
                lambda: send_notification_email_task.delay(
                    recipient_email=user.email,
                    context=email_context,
                    notification_code="EMAIL_CONFIRMATION",
                    title="Welcome! Confirm your email registration",
                    user_id=user.id,
                    document_id=None,
                )
            )

            return user
        except IntegrityError:
            raise serializers.ValidationError({"email": "Email already exists"})


class ConfirmEmailSerializer(serializers.Serializer):
    """
    Serializer used only for validating email confirmation token input.
    """

    token = serializers.UUIDField()


class EmailConfirmationSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for EmailConfirmation model.
    Used for admin/debug purposes (not for confirm-email flow).
    """

    class Meta:
        model = EmailConfirmation
        fields = [
            "id",
            "user",
            "token",
            "created_at",
            "expires_at",
            "is_confirmed",
        ]
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for user profile.
    Used for GET /profile/
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "avatar",
            "is_2fa_enabled",
            "two_factor_method",
        ]


class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating profile data.
    Used for PUT/PATCH /profile/
    """

    avatar = serializers.ImageField(required=False)

    first_name = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=150,
    )

    last_name = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=150,
    )

    current_password = serializers.CharField(
        required=False,
        write_only=True,
    )

    new_password = serializers.CharField(
        required=False,
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "avatar",
            "current_password",
            "new_password",
        ]

    def validate_avatar(self, value):
        """Validate avatar size and content type."""

        if value.size > settings.AVATAR_MAX_SIZE:
            raise serializers.ValidationError("Max size 5MB")

        content_type = getattr(value, "content_type", None)

        allowed_types = settings.ALLOWED_AVATAR_TYPES

        # type check

        if content_type not in allowed_types:
            raise serializers.ValidationError("Only JPEG and PNG are allowed")

        return value

    def validate_new_password(self, value):
        """Validate the new password against Django rules."""

        validate_password(value, user=self.instance)
        return value

    def validate(self, attrs):
        """Validate password change requirements."""

        if "new_password" in attrs and "current_password" not in attrs:
            raise serializers.ValidationError(
                {
                    "current_password": (
                        "Current password is required to set a new password."
                    )
                }
            )

        if "current_password" in attrs:
            if not self.instance.check_password(attrs["current_password"]):
                raise serializers.ValidationError(
                    {"current_password": "Current password is incorrect."}
                )

        return attrs

    def update(self, instance, validated_data):
        """Update profile fields and optionally change the password."""

        validated_data.pop("current_password", None)
        new_password = validated_data.pop("new_password", None)

        instance = super().update(instance, validated_data)

        if new_password:
            instance.set_password(new_password)
            instance.save(update_fields=["password"])

        return instance


class GoogleAuthSerializer(serializers.Serializer):
    """Authenticate or register a user with Google."""

    id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate Google ID token and return user information."""

        try:
            google_data = id_token.verify_oauth2_token(
                attrs["id_token"],
                requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except (ValueError, GoogleAuthError):
            raise serializers.ValidationError({"id_token": "Invalid Google ID token."})

        if google_data.get("email_verified") is not True:
            raise serializers.ValidationError(
                {"id_token": "Google email is not verified."}
            )

        attrs["google_data"] = google_data
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        google_data = validated_data["google_data"]
        google_id = google_data["sub"]
        email = google_data["email"].lower()
        first_name = google_data.get("given_name", "")
        last_name = google_data.get("family_name", "")

        social_account = (
            SocialAccount.objects.select_for_update()
            .filter(provider=SocialAccount.PROVIDER.GOOGLE, provider_user_id=google_id)
            .select_related("user")
            .first()
        )

        if social_account:
            user = social_account.user

            if user.is_blocked:
                raise serializers.ValidationError(
                    {"id_token": "This account has been blocked."}
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    {"id_token": "This account is inactive."}
                )

            return user

        try:
            user = User.objects.filter(email__iexact=email).first()

            if user is None:
                user = User.objects.create_user(
                    email=email,
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                    registration_method=User.REGISTRATION_METHOD.GOOGLE,
                )
            else:
                if user.is_blocked:
                    raise serializers.ValidationError(
                        {"id_token": "This account has been blocked."}
                    )

                update_fields = []

                if not user.is_active:
                    user.is_active = True
                    update_fields.append("is_active")

                if not user.first_name and first_name:
                    user.first_name = first_name
                    update_fields.append("first_name")

                if not user.last_name and last_name:
                    user.last_name = last_name
                    update_fields.append("last_name")

                if update_fields:
                    user.save(update_fields=update_fields)

            SocialAccount.objects.create(
                user=user,
                provider=SocialAccount.PROVIDER.GOOGLE,
                provider_user_id=google_id,
            )
        except IntegrityError:
            # Lost the race to a concurrent request — the SocialAccount
            # (or User with this email) now exists, fetch and return it.
            social_account = SocialAccount.objects.select_related("user").get(
                provider=SocialAccount.PROVIDER.GOOGLE,
                provider_user_id=google_id,
            )
            user = social_account.user

            if user.is_blocked:
                raise serializers.ValidationError(
                    {"id_token": "This account has been blocked."}
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    {"id_token": "This account is inactive."}
                )

            return user

        return user


class TokenResponseSerializer(serializers.Serializer):
    """Response shape for successful JWT auth (login, Google auth)."""

    refresh = serializers.CharField()
    access = serializers.CharField()
    email = serializers.EmailField()
    id = serializers.IntegerField()


class RegisterResponseSerializer(serializers.Serializer):
    """Response shape for successful registration."""

    message = serializers.CharField()
    status = serializers.CharField()
