from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.accounts.models import SocialAccount, User

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
    assert user.registration_method == User.REGISTRATION_GOOGLE

    social_account = SocialAccount.objects.get(user=user)

    assert social_account.provider == SocialAccount.PROVIDER_GOOGLE
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
        provider=SocialAccount.PROVIDER_GOOGLE,
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
        provider=SocialAccount.PROVIDER_GOOGLE,
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
            provider=SocialAccount.PROVIDER_GOOGLE,
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
