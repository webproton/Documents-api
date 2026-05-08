from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import EmailConfirmation
from .serializers import (
    ConfirmEmailSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
)
from .services import register_user_flow


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"id": request.user.id})


class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
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
    serializer_class = LoginSerializer


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

    def post(self, request):
        # Validate input data
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create user but keep account inactive until email confirmation
        # Create email confirmation token + trigger email sending
        register_user_flow(**serializer.validated_data)

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

    def post(self, request):
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
