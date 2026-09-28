from django.urls import path

from .views import (
    ConfirmEmailAPIView,
    ConfirmPhoneAPIView,
    GoogleAuthAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    ProfileAPIView,
    RegisterAPIView,
    RequestPhoneConfirmationAPIView,
    Resend2FAView,
    SafeTokenRefreshView,
    Toggle2FAView,
    TwoFactorVerifyView,
    UserDeviceListView,
    UserDeviceRevokeAllView,
    UserDeviceRevokeView,
)

app_name = "apps.accounts"

urlpatterns = [
    # --------------------------------------------------------------------------
    # Authentication (Login, Register, OAuth, Tokens)
    # --------------------------------------------------------------------------
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/confirm-email/", ConfirmEmailAPIView.as_view(), name="confirm-email"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/social/google/", GoogleAuthAPIView.as_view(), name="google-auth"),
    path("auth/refresh/", SafeTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    # --------------------------------------------------------------------------
    # 2FA Authentication Flow (Step 2 during login)
    # --------------------------------------------------------------------------
    path("auth/2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path("auth/2fa/resend/", Resend2FAView.as_view(), name="2fa-resend"),
    # --------------------------------------------------------------------------
    # User Profile & Account Data
    # --------------------------------------------------------------------------
    path("auth/me/", MeAPIView.as_view(), name="me"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
    # --------------------------------------------------------------------------
    # Profile Security & 2FA Management
    # --------------------------------------------------------------------------
    path(
        "profile/phone/request-confirmation/",
        RequestPhoneConfirmationAPIView.as_view(),
        name="phone-request-confirmation",
    ),
    path(
        "profile/phone/confirm/",
        ConfirmPhoneAPIView.as_view(),
        name="phone-confirm",
    ),
    path("profile/2fa/toggle/", Toggle2FAView.as_view(), name="profile-2fa-toggle"),
    # --------------------------------------------------------------------------
    # Device / Session Management
    # --------------------------------------------------------------------------
    path("devices/", UserDeviceListView.as_view(), name="device-list"),
    path(
        "devices/revoke-all/",
        UserDeviceRevokeAllView.as_view(),
        name="device-revoke-all",
    ),
    path(
        "devices/<int:pk>/revoke/",
        UserDeviceRevokeView.as_view(),
        name="device-revoke",
    ),
]
