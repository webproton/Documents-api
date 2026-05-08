from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import EmailConfirmation, User
from .tasks import send_confirmation_email_task


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        # get user

        # generate token
        data = super().validate(attrs)

        user = self.user  # уже установлен SimpleJWT

        if not user.is_active:
            raise serializers.ValidationError("Email is not confirmed")

        data["email"] = user.email
        data["id"] = user.id
        return data


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    def validate_password(self, value):
        validate_password(value)  # Django rules
        return value

    def validate_email(self, value):
        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")

        return value

    def validate(self, attrs):
        if attrs["email"] in attrs["password"]:
            raise serializers.ValidationError("Password too similar to email")
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=validated_data["email"],
                    password=validated_data["password"],
                    is_active=False,
                )

                confirmation = EmailConfirmation.create_email_confirmation(user)

            transaction.on_commit(
                lambda: send_confirmation_email_task.delay(
                    user_email=user.email,
                    token=str(confirmation.token),
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
