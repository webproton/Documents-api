import uuid
from unittest.mock import patch

import pytest
from apps.accounts.tests.factories import PhoneConfirmationFactory, UserFactory
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from app.apps.accounts.models import PhoneConfirmation, User


@pytest.fixture(autouse=True)
def clear_redis_cache():
    """Automatically clears the Redis cache before each test to reset cooldowns."""
    cache.clear()


# ==============================================================================
# LoginAPIView Tests
# ==============================================================================


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
