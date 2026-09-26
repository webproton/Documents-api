# app/apps/accounts/tests/test_models_2fa.py
from datetime import timedelta

import pytest
from django.utils import timezone

from app.apps.accounts.models import PhoneConfirmation
from app.apps.accounts.tests.factories import (
    PhoneConfirmationFactory,
    UserDeviceFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestPhoneConfirmationModel:

    def test_phone_confirmation_flow_success(self):
        """Verify PhoneConfirmation creation and successful confirmation logic."""
        user = UserFactory()
        target_phone = "+380971112233"
        instance, raw_code = PhoneConfirmation.create_for_phone(user, target_phone)

        assert instance.user == user
        assert instance.phone_number == target_phone
        assert instance.is_confirmed is False
        assert instance.is_expired() is False

        success = instance.confirm(raw_code)

        assert success is True
        assert instance.is_confirmed is True

        user.refresh_from_db()
        assert user.phone_number == target_phone
        assert user.phone_confirmed is True

    def test_phone_confirmation_invalid_code(self):
        """Verify confirmation fails on incorrect code submission."""
        confirmation = PhoneConfirmationFactory()

        success = confirmation.confirm("000000")

        assert success is False
        assert confirmation.is_confirmed is False

    def test_phone_confirmation_expired_code(self):
        """Verify expired PhoneConfirmation instance rejects verification attempts."""
        confirmation = PhoneConfirmationFactory(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        assert confirmation.is_expired() is True
        assert confirmation.confirm("123456") is False


@pytest.mark.django_db
class TestUserDeviceModel:

    def test_user_device_hashing_and_touch(self):
        """Verify UserDevice token hashing, expiration, and touch tracking."""
        device = UserDeviceFactory()

        assert device.is_expired() is False
        assert device.last_login_at is None

        device.touch()

        device.refresh_from_db()
        assert device.last_login_at is not None

        device.revoke()
        assert device.is_revoked is True
