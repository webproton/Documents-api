from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

from app.apps.notifications.tasks import send_notification_email_task

from .models import EmailConfirmation, SocialAccount, User


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

        data = super().validate(attrs)

        data["email"] = self.user.email
        data["id"] = self.user.id
        return data


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
