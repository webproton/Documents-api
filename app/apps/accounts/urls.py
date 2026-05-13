from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ConfirmEmailAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    ProfileAPIView,
    RegisterAPIView,
)

app_name = "apps.accounts"

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/confirm-email/", ConfirmEmailAPIView.as_view(), name="confirm-email"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeAPIView.as_view(), name="me"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
]
