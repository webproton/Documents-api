"""
Every login is a device session (new_task.md, section 5):
JWTs are bound to the session, ending it revokes them on the server.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.accounts.tests.factories import UserDeviceFactory, UserFactory
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from app.apps.accounts.models import UserDevice

PASSWORD = "SecurePass123!"


@pytest.fixture(autouse=True)
def clear_redis_cache():
    cache.clear()


@pytest.fixture
def make_user():
    def _make(**kwargs):
        user = UserFactory(**kwargs)
        user.set_password(PASSWORD)
        user.save()
        return user

    return _make


def login(client, user, device_token=None):
    headers = {"HTTP_X_DEVICE_TOKEN": device_token} if device_token else {}
    return client.post(
        reverse("apps.accounts:login"),
        {"email": user.email, "password": PASSWORD},
        format="json",
        **headers,
    )


def client_with(access, device_token=None):
    """A separate browser: its own Authorization and X-Device-Token."""
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
    if device_token:
        headers["HTTP_X_DEVICE_TOKEN"] = device_token
    client.credentials(**headers)
    return client


def profile_status(client):
    return client.get(reverse("apps.accounts:profile")).status_code


def refresh_status(refresh):
    response = APIClient().post(
        reverse("apps.accounts:token_refresh"), {"refresh": refresh}, format="json"
    )
    return response.status_code, response.data


@pytest.mark.django_db
class TestLoginCreatesSession:
    def test_login_without_2fa_creates_an_untrusted_session(self, make_user):
        user = make_user()

        response = login(APIClient(), user)

        assert response.status_code == status.HTTP_200_OK
        device = UserDevice.objects.get(user=user)
        assert response.data["device_token"]
        assert UserDevice.hash_token(response.data["device_token"]) == (
            device.device_token_hash
        )
        # Tokens are bound to the session
        assert AccessToken(response.data["access"])["device_id"] == device.id
        assert RefreshToken(response.data["refresh"])["device_id"] == device.id
        assert device.is_trusted is False

    def test_current_session_is_listed(self, make_user):
        user = make_user()
        data = login(APIClient(), user).data

        browser = client_with(data["access"], data["device_token"])
        response = browser.get(reverse("apps.accounts:device-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        item = response.data[0]
        assert item["is_current"] is True
        assert item["is_active_session"] is True
        assert item["is_trusted"] is False

    def test_login_again_from_same_browser_reuses_the_session(self, make_user):
        user = make_user()
        first = login(APIClient(), user).data

        second = login(APIClient(), user, device_token=first["device_token"]).data

        assert UserDevice.objects.filter(user=user).count() == 1
        # Device token is rotated on every login
        assert second["device_token"] != first["device_token"]


@pytest.mark.django_db
class TestEndingSessions:
    def test_revoked_device_loses_access_and_refresh(self, make_user):
        user = make_user()
        laptop = login(APIClient(), user).data
        phone = login(APIClient(), user).data
        laptop_client = client_with(laptop["access"], laptop["device_token"])
        phone_device = UserDevice.objects.get(
            device_token_hash=UserDevice.hash_token(phone["device_token"])
        )

        response = laptop_client.post(
            reverse("apps.accounts:device-revoke", kwargs={"pk": phone_device.pk})
        )

        assert response.status_code == status.HTTP_200_OK
        assert profile_status(client_with(phone["access"])) == 401
        assert refresh_status(phone["refresh"])[0] == 401
        # The laptop keeps working
        assert profile_status(laptop_client) == 200

    def test_revoke_all_keeps_only_the_current_session(self, make_user):
        user = make_user()
        current = login(APIClient(), user).data
        other_1 = login(APIClient(), user).data
        other_2 = login(APIClient(), user).data
        current_client = client_with(current["access"], current["device_token"])

        current_client.post(reverse("apps.accounts:device-revoke-all"))

        assert profile_status(current_client) == 200
        assert profile_status(client_with(other_1["access"])) == 401
        assert profile_status(client_with(other_2["access"])) == 401

    def test_revoking_a_trusted_device_requires_2fa_again(self, make_user):
        user = make_user(is_2fa_enabled=True)
        raw_token = "trusted-device-token"
        device = UserDeviceFactory(
            user=user,
            device_token_hash=UserDevice.hash_token(raw_token),
        )
        assert login(APIClient(), user, raw_token).status_code == 200

        device.revoke()

        response = login(APIClient(), user, raw_token)
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_logout_ends_the_session_immediately(self, make_user):
        user = make_user()
        data = login(APIClient(), user).data
        browser = client_with(data["access"], data["device_token"])

        response = browser.post(
            reverse("apps.accounts:logout"), {"refresh": data["refresh"]}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        # Access token stops working right away, not after 60 minutes
        assert profile_status(browser) == 401
        # An untrusted session disappears from the list
        assert not UserDevice.objects.active().filter(user=user).exists()


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.TwoFactorRedisManager.verify_otp_code")
class TestTrustedDevices:
    def verify(self, mock_verify, user, remember):
        mock_verify.return_value = (True, user.id, "")
        return APIClient().post(
            reverse("apps.accounts:2fa-verify"),
            {
                "pre_auth_token": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "code": "123456",
                "remember_device": remember,
            },
            format="json",
        )

    def test_remembered_device_is_trusted_for_90_days(self, mock_verify, make_user):
        user = make_user(is_2fa_enabled=True)

        data = self.verify(mock_verify, user, remember=True).data

        device = UserDevice.objects.get(user=user)
        expected = timezone.now() + timedelta(days=90)
        assert abs(device.trusted_until - expected) < timedelta(minutes=1)
        # Next login from this browser skips 2FA
        assert login(APIClient(), user, data["device_token"]).status_code == 200

    def test_not_remembered_device_still_gets_a_session(self, mock_verify, make_user):
        user = make_user(is_2fa_enabled=True)

        data = self.verify(mock_verify, user, remember=False).data

        device = UserDevice.objects.get(user=user)
        assert device.is_trusted is False
        assert AccessToken(data["access"])["device_id"] == device.id
        # Not trusted → 2FA again on the next login
        assert login(APIClient(), user, data["device_token"]).status_code == 202

    def test_trust_expires_after_90_days(self, mock_verify, make_user):
        user = make_user(is_2fa_enabled=True)
        data = self.verify(mock_verify, user, remember=True).data
        UserDevice.objects.filter(user=user).update(
            trusted_until=timezone.now() - timedelta(seconds=1)
        )

        assert login(APIClient(), user, data["device_token"]).status_code == 202

    def test_logout_keeps_a_trusted_device(self, mock_verify, make_user):
        user = make_user(is_2fa_enabled=True)
        data = self.verify(mock_verify, user, remember=True).data
        browser = client_with(data["access"], data["device_token"])

        browser.post(
            reverse("apps.accounts:logout"), {"refresh": data["refresh"]}, format="json"
        )

        device = UserDevice.objects.get(user=user)
        assert device.is_trusted is True
        assert device.is_expired() is True  # session itself is over
        assert UserDevice.objects.active().filter(id=device.id).exists()
        # Spec: re-login from this browser within 90 days skips 2FA
        assert login(APIClient(), user, data["device_token"]).status_code == 200


@pytest.mark.django_db
class TestRefresh:
    def test_refresh_keeps_session_and_extends_it(self, make_user):
        user = make_user()
        data = login(APIClient(), user).data
        device = UserDevice.objects.get(user=user)
        UserDevice.objects.filter(id=device.id).update(
            expires_at=timezone.now() + timedelta(minutes=5)
        )

        code, refreshed = refresh_status(data["refresh"])

        assert code == 200
        assert AccessToken(refreshed["access"])["device_id"] == device.id
        assert RefreshToken(refreshed["refresh"])["device_id"] == device.id
        device.refresh_from_db()
        assert device.expires_at > timezone.now() + timedelta(hours=23)

    def test_tokens_without_session_claim_still_work(self, make_user):
        """Tokens issued before sessions existed have no device_id claim."""
        user = make_user()
        refresh = RefreshToken.for_user(user)

        assert profile_status(client_with(str(refresh.access_token))) == 200
        assert refresh_status(str(refresh))[0] == 200
