from unittest.mock import patch

import pytest
from apps.accounts.tests.factories import UserDeviceFactory, UserFactory
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from app.apps.accounts.models import SocialAccount, User, UserDevice

GOOGLE_DATA = {
    "sub": "google-123",
    "email": "google@test.com",
    "email_verified": True,
    "given_name": "Google",
    "family_name": "User",
}


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_creates_user(mock_verify, api_client, settings):
    mock_verify.return_value = GOOGLE_DATA
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

    user = User.objects.get(email="google@test.com")

    assert user.is_active is True
    assert user.first_name == "Google"
    assert user.last_name == "User"
    assert user.registration_method == User.REGISTRATION_METHOD.GOOGLE

    social_account = SocialAccount.objects.get(user=user)

    assert social_account.provider == SocialAccount.PROVIDER.GOOGLE
    assert social_account.provider_user_id == "google-123"


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_links_existing_user(
    mock_verify,
    api_client,
    user,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email": user.email,
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    user.is_active = True
    user.first_name = ""
    user.last_name = ""
    user.save()

    user_id = user.id

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

    user.refresh_from_db()

    assert user.id == user_id
    assert user.is_active is True
    assert user.first_name == "Google"
    assert user.last_name == "User"

    assert SocialAccount.objects.filter(
        user=user,
        provider=SocialAccount.PROVIDER.GOOGLE,
        provider_user_id="google-123",
    ).exists()


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_does_not_overwrite_existing_profile(
    mock_verify,
    api_client,
    user,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email": user.email,
        "given_name": "Google",
        "family_name": "GoogleSurname",
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    user.is_active = True
    user.first_name = "Existing"
    user.last_name = "Name"
    user.save()

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.first_name == "Existing"
    assert user.last_name == "Name"


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_existing_social_account(
    mock_verify,
    api_client,
    user,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email": user.email,
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    user.is_active = True
    user.save()

    SocialAccount.objects.create(
        user=user,
        provider=SocialAccount.PROVIDER.GOOGLE,
        provider_user_id="google-123",
    )

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

    assert (
        SocialAccount.objects.filter(
            provider=SocialAccount.PROVIDER.GOOGLE,
            provider_user_id="google-123",
        ).count()
        == 1
    )


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_invalid_token(
    mock_verify,
    api_client,
    settings,
):
    mock_verify.side_effect = ValueError("Invalid token")
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "invalid-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_token" in response.data["errors"]


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_unverified_email(
    mock_verify,
    api_client,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email_verified": False,
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_token" in response.data["errors"]


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_existing_inactive_user_becomes_active(
    mock_verify,
    api_client,
    user,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email": user.email,
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    user.is_active = False
    user.save()

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.is_active is True


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_rejects_blocked_user(
    mock_verify,
    api_client,
    user,
    settings,
):
    mock_verify.return_value = {
        **GOOGLE_DATA,
        "email": user.email,
    }
    settings.GOOGLE_CLIENT_ID = "test-client-id"

    user.is_active = True
    user.is_blocked = True
    user.save()

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_token" in response.data["errors"]


# ==============================================================================
# Google sign-in follows the same 2FA rules as password login
# ==============================================================================


@pytest.fixture
def google_2fa_user(settings):
    """Existing user with email 2FA enabled, signing in with Google."""
    cache.clear()  # reset 2FA resend cooldowns stored in Redis
    settings.GOOGLE_CLIENT_ID = "test-client-id"
    return UserFactory(email=GOOGLE_DATA["email"], is_2fa_enabled=True)


@pytest.mark.django_db
@patch("app.apps.accounts.services.send_email_otp_task")
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_requires_2fa_on_untrusted_device(
    mock_verify,
    mock_email_task,
    api_client,
    google_2fa_user,
    django_capture_on_commit_callbacks,
):
    mock_verify.return_value = GOOGLE_DATA

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse("apps.accounts:google-auth"),
            {"id_token": "valid-google-token"},
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["requires_2fa"] is True
    assert response.data["delivery_method"] == User.TWO_FACTOR_METHOD.EMAIL
    assert "pre_auth_token" in response.data
    # No JWT before the second factor is verified
    assert "access" not in response.data
    mock_email_task.delay.assert_called_once()
    assert mock_email_task.delay.call_args.args[0] == google_2fa_user.id


@pytest.mark.django_db
@patch("app.apps.accounts.serializers.id_token.verify_oauth2_token")
def test_google_auth_skips_2fa_on_trusted_device(
    mock_verify, api_client, google_2fa_user
):
    mock_verify.return_value = GOOGLE_DATA
    raw_device_token = "trusted-device-token-123"
    device = UserDeviceFactory(
        user=google_2fa_user,
        device_token_hash=UserDevice.hash_token(raw_device_token),
        last_login_at=None,
    )

    response = api_client.post(
        reverse("apps.accounts:google-auth"),
        {"id_token": "valid-google-token"},
        format="json",
        HTTP_X_DEVICE_TOKEN=raw_device_token,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["requires_2fa"] is False
    assert "access" in response.data
    device.refresh_from_db()
    assert device.last_login_at is not None
