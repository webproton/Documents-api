import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.accounts.tests.factories import (
    PhoneConfirmationFactory,
    UserDeviceFactory,
    UserFactory,
)
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app.apps.accounts.models import PhoneConfirmation, User, UserDevice


@pytest.fixture(autouse=True)
def clear_redis_cache():
    """Automatically clears the Redis cache before each test to reset cooldowns."""
    cache.clear()


# ==============================================================================
# LoginAPIView Tests
# ==============================================================================


@pytest.mark.django_db
def test_login_bypasses_2fa_with_valid_trusted_device(api_client):
    """
    If 2FA is enabled for the user, but a valid X-Device-Token header is provided
    for a trusted device, 2FA verification is bypassed and
    JWT tokens are returned directly.
    """
    password = "SecurePass123!"
    raw_device_token = "valid-secret-device-token-12345"

    # Create a user with 2FA enabled using UserFactory
    user = UserFactory(is_2fa_enabled=True)
    user.set_password(password)
    user.save()

    # Create a trusted device linked to the user using UserDeviceFactory
    device = UserDeviceFactory(
        user=user,
        device_token_hash=UserDevice.hash_token(raw_device_token),
        expires_at=timezone.now() + timedelta(days=30),
        is_revoked=False,
    )

    url = reverse("apps.accounts:login")

    # Send a POST request with the device token in the HTTP header
    response = api_client.post(
        url,
        {"email": user.email, "password": password},
        format="json",
        HTTP_X_DEVICE_TOKEN=raw_device_token,
    )

    # Verify successful HTTP 200 OK response
    assert response.status_code == status.HTTP_200_OK
    # Ensure 2FA is not required
    assert response.data["requires_2fa"] is False
    # Ensure access and refresh JWT tokens are present
    assert "access" in response.data
    assert "refresh" in response.data

    # Refresh the device instance from the database
    device.refresh_from_db()
    # Verify that touch() was executed and updated the last login timestamp
    assert device.last_login_at is not None


@pytest.mark.django_db
def test_login_requires_2fa_when_device_token_is_revoked(api_client):
    """
    If a device token is provided but the device is revoked (is_revoked=True),
    the device is ignored and 2FA is required.
    """
    password = "SecurePass123!"
    raw_token = "revoked-device-token-xyz"

    # Create a user with 2FA enabled
    user = UserFactory(is_2fa_enabled=True)
    user.set_password(password)
    user.save()

    # Create a revoked device in the database using UserDeviceFactory
    UserDeviceFactory(
        user=user,
        device_token_hash=UserDevice.hash_token(raw_token),
        expires_at=timezone.now() + timedelta(days=30),
        is_revoked=True,
    )

    url = reverse("apps.accounts:login")

    # Perform a login request using the revoked device token
    response = api_client.post(
        url,
        {"email": user.email, "password": password},
        format="json",
        HTTP_X_DEVICE_TOKEN=raw_token,
    )

    # Expect HTTP 202 ACCEPTED (2FA step required)
    assert response.status_code == status.HTTP_202_ACCEPTED
    # Verify that 2FA is required
    assert response.data["requires_2fa"] is True
    # Verify the presence of the pre_auth_token for the next authentication step
    assert "pre_auth_token" in response.data


@pytest.mark.django_db
def test_login_bypasses_2fa_if_2fa_disabled_even_without_device(api_client):
    """
    Verifies that if 2FA is disabled (is_2fa_enabled = False),
    login succeeds without 2FA even without a trusted device header.
    """
    password = "SecurePass123!"

    # Create a user with 2FA disabled using UserFactory
    user = UserFactory(is_2fa_enabled=False)
    user.set_password(password)
    user.save()

    url = reverse("apps.accounts:login")

    # Send a login request from a new device (without X-Device-Token header)
    response = api_client.post(
        url,
        {"email": user.email, "password": password},
        format="json",
    )

    # Expect HTTP 200 OK
    assert response.status_code == status.HTTP_200_OK
    # Ensure 2FA is not required
    assert response.data["requires_2fa"] is False
    # Ensure access and refresh tokens are issued
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
@patch("app.apps.accounts.tasks.send_email_otp_task.delay")
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.create_2fa_session")
def test_login_requires_2fa_email(
    mock_create_session,
    mock_email_task,
    api_client,
    user,
    django_capture_on_commit_callbacks,
):
    user.set_password("SecurePass123!")
    user.is_2fa_enabled = True
    user.two_factor_method = User.TWO_FACTOR_METHOD.EMAIL
    user.save()

    valid_uuid = str(uuid.uuid4())
    mock_create_session.return_value = (valid_uuid, "123456")

    url = reverse("apps.accounts:login")

    # Execute a request inside the interceptor on_commit callbacks
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            url,
            {"email": user.email, "password": "SecurePass123!"},
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["requires_2fa"] is True
    assert response.data["pre_auth_token"] == valid_uuid
    assert response.data["delivery_method"] == User.TWO_FACTOR_METHOD.EMAIL

    mock_email_task.assert_called_once_with(user.id, "123456")


@pytest.mark.django_db
@patch("app.apps.accounts.tasks.send_sms_task.delay")
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.create_2fa_session")
def test_login_requires_2fa_sms(
    mock_create_session, mock_sms_task, api_client, django_capture_on_commit_callbacks
):
    user = UserFactory(phone_confirmed_user=True)
    user.set_password("SecurePass123!")
    user.is_2fa_enabled = True
    user.two_factor_method = User.TWO_FACTOR_METHOD.SMS
    user.save()

    valid_uuid = str(uuid.uuid4())
    mock_create_session.return_value = (valid_uuid, "654321")

    url = reverse("apps.accounts:login")

    # Execute a request inside the interceptor on_commit callbacks
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            url,
            {"email": user.email, "password": "SecurePass123!"},
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["requires_2fa"] is True
    assert response.data["delivery_method"] == User.TWO_FACTOR_METHOD.SMS

    # Check the Celery task call after running the on_commit
    mock_sms_task.assert_called_once_with(user.phone_number, "654321")


# ==============================================================================
# TwoFactorVerifyView Tests
# ==============================================================================


@pytest.mark.django_db
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.verify_otp_code")
def test_2fa_verify_issues_device_token_when_remember_device_true(
    mock_verify_otp, api_client
):
    """
    When confirming 2FA with remember_device = True, a device_token is issued
    and a corresponding UserDevice record is created in the database.
    """
    # Create a test user via factory
    user = UserFactory()

    # Mock successful OTP verification returning the user's ID
    mock_verify_otp.return_value = (True, user.id, "")
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-verify")

    # Send verification request with remember_device = True
    response = api_client.post(
        url,
        {
            "pre_auth_token": valid_uuid,
            "code": "123456",
            "remember_device": True,
        },
        format="json",
        HTTP_USER_AGENT="Pytest-User-Agent",
    )

    # Verify HTTP 200 OK status
    assert response.status_code == status.HTTP_200_OK
    # Verify that raw device_token is present in the response
    assert "device_token" in response.data

    # Extract raw token and compute its hash
    raw_token = response.data["device_token"]
    token_hash = UserDevice.hash_token(raw_token)

    # Retrieve the device record from the DB by hash
    device_in_db = UserDevice.objects.filter(
        user=user, device_token_hash=token_hash
    ).first()

    # Assert device creation and correct User-Agent persistence
    assert device_in_db is not None
    assert device_in_db.user_agent == "Pytest-User-Agent"


@pytest.mark.django_db
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.verify_otp_code")
def test_2fa_verify_success(mock_verify_otp, api_client, user):
    mock_verify_otp.return_value = (True, user.id, "")
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-verify")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid, "code": "123456"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.verify_otp_code")
def test_2fa_verify_invalid_code(mock_verify_otp, api_client):
    mock_verify_otp.return_value = (False, None, "Invalid or expired OTP code.")
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-verify")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid, "code": "000000"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.verify_otp_code")
def test_2fa_verify_user_not_found(mock_verify_otp, api_client):
    mock_verify_otp.return_value = (True, 999999, "")  # Non-existent user ID
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-verify")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid, "code": "123456"},
        format="json",
    )

    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_404_NOT_FOUND,
    )


# ==============================================================================
# Resend2FAView Tests
# ==============================================================================


@pytest.mark.django_db
@patch("app.apps.accounts.tasks.send_email_otp_task.delay")
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.resend_2fa_code")
def test_resend_2fa_success_email(mock_resend_2fa, mock_email_task, api_client, user):
    mock_resend_2fa.return_value = (
        True,
        "888999",
        user.id,
        User.TWO_FACTOR_METHOD.EMAIL,
        "",
    )
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-resend")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    mock_email_task.assert_called_once_with(user.id, "888999")


@pytest.mark.django_db
@patch("app.apps.accounts.tasks.send_sms_task.delay")
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.resend_2fa_code")
def test_resend_2fa_success_sms(mock_resend_2fa, mock_sms_task, api_client, user):
    user.phone_number = "+380971112233"
    user.phone_confirmed = True
    user.save()

    mock_resend_2fa.return_value = (
        True,
        "777111",
        user.id,
        User.TWO_FACTOR_METHOD.SMS,
        "",
    )
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-resend")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    mock_sms_task.assert_called_once_with(user.phone_number, "777111")


@pytest.mark.django_db
@patch(
    "app.apps.accounts.redis_manager.TwoFactorRedisManager.is_resend_on_cooldown",
    return_value=False,
)
@patch("app.apps.accounts.redis_manager.TwoFactorRedisManager.resend_2fa_code")
def test_resend_2fa_failed_session(mock_resend_2fa, mock_cooldown, api_client):
    mock_resend_2fa.return_value = (False, None, None, None, "Session expired.")
    valid_uuid = str(uuid.uuid4())

    url = reverse("apps.accounts:2fa-resend")
    response = api_client.post(
        url,
        {"pre_auth_token": valid_uuid},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# RequestPhoneConfirmationAPIView Tests
# ==============================================================================


@pytest.mark.django_db
@patch("app.apps.accounts.tasks.send_sms_task.delay")
def test_request_phone_confirmation_success(
    mock_sms_task, api_client, user, django_capture_on_commit_callbacks
):
    api_client.force_authenticate(user=user)

    PhoneConfirmationFactory(user=user, is_confirmed=False)

    url = reverse("apps.accounts:phone-request-confirmation")
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            url,
            {"phone_number": "+380971234567"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK

    active_confirmations = PhoneConfirmation.objects.filter(
        user=user, is_confirmed=False
    )
    assert active_confirmations.count() == 1
    assert active_confirmations.first().phone_number == "+380971234567"

    mock_sms_task.assert_called_once()


@pytest.mark.django_db
def test_request_phone_confirmation_unauthorized(api_client):
    url = reverse("apps.accounts:phone-request-confirmation")
    response = api_client.post(url, {"phone_number": "+380971234567"}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# ConfirmPhoneAPIView Tests
# ==============================================================================


@pytest.mark.django_db
def test_confirm_phone_success(api_client, user):
    api_client.force_authenticate(user=user)
    PhoneConfirmationFactory(user=user, is_confirmed=False)

    with patch.object(PhoneConfirmation, "confirm", return_value=True):
        url = reverse("apps.accounts:phone-confirm")
        response = api_client.post(
            url,
            {"code": "123456"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_confirm_phone_invalid_code(api_client, user):
    api_client.force_authenticate(user=user)
    PhoneConfirmationFactory(user=user, is_confirmed=False)

    with patch.object(PhoneConfirmation, "confirm", return_value=False):
        url = reverse("apps.accounts:phone-confirm")
        response = api_client.post(
            url,
            {"code": "000000"},
            format="json",
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# Toggle2FAView Tests
# ==============================================================================


@pytest.mark.django_db
@patch(
    "app.apps.accounts.redis_manager.TwoFactorRedisManager.is_resend_on_cooldown",
    return_value=False,
)
def test_toggle_2fa_enable_email(mock_cooldown, api_client, user):
    user.set_password("SecurePass123!")
    user.is_2fa_enabled = False
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile-2fa-toggle")
    payload = {
        "enable": True,
        "is_2fa_enabled": True,
        "method": User.TWO_FACTOR_METHOD.EMAIL,
        "two_factor_method": User.TWO_FACTOR_METHOD.EMAIL,
        "password": "SecurePass123!",
        "current_password": "SecurePass123!",
    }
    response = api_client.post(url, payload, format="json")

    user.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert user.is_2fa_enabled is True


@pytest.mark.django_db
@patch(
    "app.apps.accounts.redis_manager.TwoFactorRedisManager.is_resend_on_cooldown",
    return_value=False,
)
def test_toggle_2fa_disable(mock_cooldown, api_client, user):
    user.set_password("SecurePass123!")
    user.is_2fa_enabled = True
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile-2fa-toggle")
    payload = {
        "enable": False,
        "is_2fa_enabled": False,
        "password": "SecurePass123!",
        "current_password": "SecurePass123!",
    }
    response = api_client.post(url, payload, format="json")

    user.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert user.is_2fa_enabled is False


@pytest.mark.django_db
def test_toggle_2fa_enable_sms_without_confirmed_phone_fails(api_client, user):
    user.set_password("SecurePass123!")
    user.phone_number = "+380971234567"
    user.phone_confirmed = False
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile-2fa-toggle")
    response = api_client.post(
        url,
        {
            "enable": True,
            "method": User.TWO_FACTOR_METHOD.SMS,
            "current_password": "SecurePass123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_toggle_2fa_requires_correct_password(api_client, user):
    user.set_password("CorrectPassword123!")
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile-2fa-toggle")
    response = api_client.post(
        url,
        {
            "enable": True,
            "method": User.TWO_FACTOR_METHOD.EMAIL,
            "current_password": "WrongPassword123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_request_phone_confirmation_invalid_phone_format(api_client, user):
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:phone-request-confirmation")
    response = api_client.post(
        url,
        {"phone_number": "invalid-phone-string"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_confirm_phone_already_confirmed_code_fails(api_client, user):
    api_client.force_authenticate(user=user)
    PhoneConfirmationFactory(user=user, is_confirmed=True)

    url = reverse("apps.accounts:phone-confirm")
    response = api_client.post(
        url,
        {"code": "123456"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
