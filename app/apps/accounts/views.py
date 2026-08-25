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

from .models import EmailConfirmation
from .serializers import (
    ConfirmEmailSerializer,
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    SafeTokenRefreshSerializer,
    TokenResponseSerializer,
    UpdateProfileSerializer,
)


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
    """Authenticate a user and return JWT tokens."""

    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_summary="Login",
        responses={200: TokenResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


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
