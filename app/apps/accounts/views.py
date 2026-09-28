from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from app.apps.common.serializers import MessageSerializer

from .models import EmailConfirmation, UserDevice
from .serializers import (
    ConfirmEmailSerializer,
    ConfirmPhoneSerializer,
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    RequestPhoneConfirmationSerializer,
    Resend2FASerializer,
    SafeTokenRefreshSerializer,
    Toggle2FASerializer,
    TokenResponseSerializer,
    TwoFactorVerifySerializer,
    UpdateProfileSerializer,
    UserDeviceSerializer,
    _extract_raw_device_token,
)
from .throttling import (
    PhoneConfirmationRateThrottle,
    TwoFactorConfirmRateThrottle,
    TwoFactorResendRateThrottle,
)

User = get_user_model()


class TwoFactorVerifyView(APIView):
    """
    Verify 2FA OTP code and issue final JWT tokens.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [TwoFactorConfirmRateThrottle]

    @swagger_auto_schema(
        operation_summary="Verify 2FA OTP code",
        request_body=TwoFactorVerifySerializer,
        responses={
            200: "JWT tokens issued successfully.",
            400: "Invalid or expired OTP code.",
        },
    )
    def post(self, request):
        # Pass request in context so the serializer
        # can extract client IP/User-Agent for device tracking
        serializer = TwoFactorVerifySerializer(
            data=request.data, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        # Complete OTP verification and obtain JWT pair along with optional device token
        tokens_and_device = serializer.save()
        return Response(tokens_and_device, status=status.HTTP_200_OK)


class RequestPhoneConfirmationAPIView(APIView):
    """
    Send an SMS confirmation code to a phone number the user wants
    to use for SMS-based 2FA.

    Any previous unconfirmed attempt for this user is invalidated —
    only one active code should exist at a time.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [PhoneConfirmationRateThrottle]

    @swagger_auto_schema(
        operation_summary="Request phone confirmation code",
        request_body=RequestPhoneConfirmationSerializer,
        responses={200: MessageSerializer, 400: "Invalid phone number."},
    )
    def post(self, request):
        serializer = RequestPhoneConfirmationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        response_data = serializer.save()

        return Response(response_data, status=status.HTTP_200_OK)


class ConfirmPhoneAPIView(APIView):
    """
    Verify the SMS code and mark the user's phone number as confirmed.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Confirm phone number",
        request_body=ConfirmPhoneSerializer,
        responses={200: MessageSerializer, 400: "Invalid or expired code."},
    )
    def post(self, request):
        serializer = ConfirmPhoneSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        response_data = serializer.confirm_phone()

        return Response(response_data, status=status.HTTP_200_OK)


class Toggle2FAView(APIView):
    """Enables or disables 2FA for the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Toggle 2FA settings",
        operation_description=(
            "Enable or disable 2FA authentication "
            "and update preferred delivery method."
        ),
        request_body=Toggle2FASerializer,
        responses={
            200: MessageSerializer,
            400: "Invalid password or unconfirmed phone number.",
        },
    )
    def post(self, request):
        serializer = Toggle2FASerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        response_data = serializer.toggle_2fa()

        return Response(response_data, status=status.HTTP_200_OK)


class Resend2FAView(APIView):
    """
    Resends a new OTP code if 2FA session is still active and not on cooldown.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [TwoFactorResendRateThrottle]

    @swagger_auto_schema(
        operation_summary="Resend 2FA verification code",
        operation_description=(
            "Issue a new OTP via SMS or" "Email using active pre-authorization token."
        ),
        request_body=Resend2FASerializer,
        responses={
            200: MessageSerializer,
            400: "Invalid session, expired token, or rate limit exceeded.",
        },
    )
    def post(self, request):
        serializer = Resend2FASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = serializer.resend_code()

        return Response(response_data, status=status.HTTP_200_OK)


class SafeTokenRefreshView(TokenRefreshView):
    """Refresh endpoint that also rejects blocked/inactive users."""

    serializer_class = SafeTokenRefreshSerializer


class ProfileAPIView(generics.RetrieveUpdateAPIView):
    """
    Endpoint for current user's profile.

    GET     → retrieve profile
    PUT     → full update
    PATCH   → partial update

    Works only with request.user (no access to other users).
    """

    permission_classes = [permissions.IsAuthenticated]

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        """Return read or update serializer based on request method."""

        if self.request.method in ("PUT", "PATCH"):
            return UpdateProfileSerializer
        return ProfileSerializer

    def get_object(self):
        """Return the currently authenticated user."""

        return self.request.user


class MeAPIView(APIView):
    """Return the current user's ID."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return the authenticated user's ID."""

        return Response({"id": request.user.id})


class LogoutAPIView(APIView):
    """Blacklist the provided refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Logout",
        operation_description="Blacklist the provided refresh token.",
        request_body=LogoutSerializer,
        responses={200: MessageSerializer, 400: "Invalid refresh token."},
    )
    def post(self, request):
        """Invalidate the user's refresh token."""

        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Logged out successfully"}, status=status.HTTP_200_OK
        )


class LoginAPIView(TokenObtainPairView):
    """
    Authenticate a user.

    If 2FA is disabled: returns JWT access and refresh tokens (200 OK).
    If 2FA is enabled: generates pre_auth_token, sends OTP code asynchronously,
    and returns pre_auth_token with 202 Accepted.
    """

    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_summary="Login user",
        responses={
            200: "JWT tokens returned (2FA disabled)",
            202: "2FA required. Returns pre_auth_token.",
            401: "Invalid credentials.",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        if data.get("requires_2fa"):
            return Response(data, status=status.HTTP_202_ACCEPTED)

        return Response(data, status=status.HTTP_200_OK)


class RegisterAPIView(APIView):
    """
    API endpoint for user registration.

    This endpoint allows a new user to register using email and password.

    Flow:
    - Validates incoming data (email, password)
    - Creates a new inactive user
    - Triggers email confirmation process (token generation and email sending)

    Permissions:
    - доступен всем (AllowAny)

    Request body:
    {
        "email": "user@example.com",
        "password": "strong_password"
    }

    Responses:
    - 201 CREATED:
        User successfully created. Email confirmation required.
    - 400 BAD REQUEST:
        Validation errors (invalid email, weak password, duplicate email, etc.)
    """

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Register a new user",
        operation_description=(
            "Create a new inactive user and send an email confirmation."
        ),
        request_body=RegisterSerializer,
        responses={201: RegisterResponseSerializer, 400: "Validation error."},
    )
    def post(self, request):
        """Validate registration data and create a new user."""

        # Validate input data
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create user but keep account inactive until email confirmation
        # Create email confirmation token + trigger email sending
        serializer.save()

        return Response(
            {
                "message": "User created. Please confirm email.",
                "status": "confirmation_required",
            },
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailAPIView(APIView):
    """
    Email confirmation endpoint.

    Confirms user's email using secure token.

    Flow:
    1. Validate token input
    2. Find EmailConfirmation(token) object
    3. Check expiration
    4. Mark confirmation as completed
    5. Activate user account

    Permissions:
    - AllowAny (token-based access)

    Request:
    {
        "token": "uuid-token"
    }

    Responses:
    - 200 OK: email successfully confirmed
    - 400 BAD REQUEST: invalid or expired token
    """

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Confirm email",
        operation_description=(
            "Validate the email confirmation token and activate the user account."
        ),
        request_body=ConfirmEmailSerializer,
        responses={200: MessageSerializer, 400: "Invalid or expired token."},
    )
    def post(self, request):
        """Validate the confirmation token and activate the user."""

        # 1. Validate input token format (UUID)
        serializer = ConfirmEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = EmailConfirmation.confirm_email_by_token(
            token=serializer.validated_data["token"]
        )

        if not result:
            return Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Success response
        return Response({"message": "Email confirmed."}, status=status.HTTP_200_OK)


class GoogleAuthAPIView(APIView):
    """Authenticate or register a user with Google."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Authenticate with Google",
        operation_description=(
            "Validate a Google ID token, create or link the user, "
            "and return JWT access and refresh tokens."
        ),
        request_body=GoogleAuthSerializer,
        responses={
            200: TokenResponseSerializer,
            400: "Invalid Google ID token or unverified email.",
        },
    )
    def post(self, request):
        """Validate Google credentials and return JWT tokens."""

        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "id": user.id,
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Device / Session Management
# ---------------------------------------------------------------------------


class UserDeviceListView(generics.ListAPIView):
    """
    GET /api/accounts/devices/

    List active (non-revoked, non-expired) trusted devices for the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserDeviceSerializer
    queryset = UserDevice.objects.active()

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class UserDeviceRevokeView(APIView):
    """
    POST /api/accounts/devices/<pk>/revoke/

    Deactivate a specific device owned by the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Revoke device",
        operation_description="Revoke a trusted device"
        "belonging to the authenticated user.",
        responses={200: MessageSerializer, 404: "Device not found."},
    )
    def post(self, request, pk):
        device = generics.get_object_or_404(request.user.devices, pk=pk)
        device.revoke()
        return Response(
            {"message": "Device revoked successfully."},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        return self.post(request, pk)


class UserDeviceRevokeAllView(APIView):
    """
    POST /api/accounts/devices/revoke-all/

    Deactivate all trusted devices for the authenticated user, except the current one.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Revoke all other devices",
        operation_description=(
            "Deactivate all trusted devices of the current user, "
            "excluding the device identified by current session token."
        ),
        responses={200: MessageSerializer},
    )
    def post(self, request):
        raw_token = _extract_raw_device_token(request)
        revoked_count = request.user.devices.revoke_all_except(raw_token)
        return Response(
            {"message": f"Revoked {revoked_count} device(s) successfully."},
            status=status.HTTP_200_OK,
        )
