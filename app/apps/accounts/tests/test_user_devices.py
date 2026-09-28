# app/apps/accounts/tests/test_user_devices.py
import secrets
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from app.apps.accounts.models import UserDevice
from app.apps.accounts.tests.factories import UserDeviceFactory, UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestUserDeviceListView:
    url = reverse("apps.accounts:device-list")

    def test_unauthenticated_forbidden(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_active_devices_only(self, authenticated_client, user):
        raw_token = secrets.token_urlsafe(32)
        token_hash = UserDevice.hash_token(raw_token)

        # Active device belonging to user
        active_device = UserDeviceFactory(
            user=user,
            device_token_hash=token_hash,
            expires_at=timezone.now() + timedelta(days=30),
            is_revoked=False,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        )
        # Expired device (should be excluded)
        UserDeviceFactory(
            user=user,
            expires_at=timezone.now() - timedelta(days=1),
            is_revoked=False,
        )
        # Revoked device (should be excluded)
        UserDeviceFactory(
            user=user,
            expires_at=timezone.now() + timedelta(days=30),
            is_revoked=True,
        )
        # Other user's device (should be excluded)
        other_user = UserFactory()
        UserDeviceFactory(user=other_user, is_revoked=False)

        # Request with header matching active_device
        response = authenticated_client.get(
            self.url,
            HTTP_X_DEVICE_TOKEN=raw_token,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["id"] == active_device.id
        assert item["is_current"] is True
        assert item["is_trusted"] is True
        assert item["device_type"] == "mobile"

    def test_is_current_via_cookie(self, authenticated_client, user):
        raw_token = secrets.token_urlsafe(32)
        device = UserDeviceFactory(
            user=user,
            device_token_hash=UserDevice.hash_token(raw_token),
            expires_at=timezone.now() + timedelta(days=10),
            is_revoked=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )

        authenticated_client.cookies["device_token"] = raw_token
        response = authenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == device.id
        assert data[0]["is_current"] is True
        assert data[0]["device_type"] == "desktop"


@pytest.mark.django_db
class TestUserDeviceRevokeView:
    def test_revoke_device_success(self, authenticated_client, user):
        device = UserDeviceFactory(user=user, is_revoked=False)
        url = reverse("apps.accounts:device-revoke", kwargs={"pk": device.pk})

        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Device revoked successfully."
        device.refresh_from_db()
        assert device.is_revoked is True

    def test_revoke_other_user_device_not_found(self, authenticated_client):
        other_user = UserFactory()
        device = UserDeviceFactory(user=other_user, is_revoked=False)
        url = reverse("apps.accounts:device-revoke", kwargs={"pk": device.pk})

        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        device.refresh_from_db()
        assert device.is_revoked is False


@pytest.mark.django_db
class TestUserDeviceRevokeAllView:
    url = reverse("apps.accounts:device-revoke-all")

    def test_revoke_all_except_current(self, authenticated_client, user):
        current_token = secrets.token_urlsafe(32)
        current_device = UserDeviceFactory(
            user=user,
            device_token_hash=UserDevice.hash_token(current_token),
            is_revoked=False,
        )
        other_device1 = UserDeviceFactory(user=user, is_revoked=False)
        other_device2 = UserDeviceFactory(user=user, is_revoked=False)

        foreign_user = UserFactory()
        foreign_device = UserDeviceFactory(user=foreign_user, is_revoked=False)

        response = authenticated_client.post(
            self.url,
            HTTP_X_DEVICE_TOKEN=current_token,
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Revoked 2 device(s)" in response.json()["message"]

        current_device.refresh_from_db()
        other_device1.refresh_from_db()
        other_device2.refresh_from_db()
        foreign_device.refresh_from_db()

        assert current_device.is_revoked is False
        assert other_device1.is_revoked is True
        assert other_device2.is_revoked is True
        assert foreign_device.is_revoked is False

    def test_revoke_all_without_token_revokes_everything(
        self, authenticated_client, user
    ):
        device1 = UserDeviceFactory(user=user, is_revoked=False)
        device2 = UserDeviceFactory(user=user, is_revoked=False)

        response = authenticated_client.post(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert "Revoked 2 device(s)" in response.json()["message"]

        device1.refresh_from_db()
        device2.refresh_from_db()
        assert device1.is_revoked is True
        assert device2.is_revoked is True
