# app/apps/accounts/tests/test_auth.py
from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.accounts.tests.factories import EmailConfirmationFactory, User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db(transaction=True)
@patch("app.apps.accounts.serializers.send_notification_email_task")
def test_register_user(mock_send_email, api_client):
    url = reverse("apps.accounts:register")

    data = {
        "email": "test@test.com",
        "password": "StrongPass123",
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "confirmation_required"

    user = User.objects.get(email=data["email"])

    assert user.is_active is False

    mock_send_email.delay.assert_called_once()


@pytest.mark.django_db
def test_register_duplicate_email(api_client, user):
    url = reverse("apps.accounts:register")

    response = api_client.post(
        url,
        {"email": user.email, "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["status"] == "error"
    assert response.data["errors"]["email"][0].code == "unique"


@pytest.mark.django_db
def test_login_success(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = True
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": user.email, "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_login_not_confirmed(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = False
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": user.email, "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert (
        response.data["errors"]["detail"]
        == "No active account found with the given credentials"
    )


@pytest.mark.django_db
def test_login_wrong_password(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = True
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": user.email, "password": "wrong"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        response.data["errors"]["detail"]
        == "No active account found with the given credentials"
    )


@pytest.mark.django_db
def test_login_user_not_found(api_client):
    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": "notexists@test.com", "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        response.data["errors"]["detail"]
        == "No active account found with the given credentials"
    )


@pytest.mark.django_db
def test_confirm_email_success(api_client):
    confirmation = EmailConfirmationFactory()
    user = confirmation.user

    url = reverse("apps.accounts:confirm-email")

    response = api_client.post(
        url,
        {"token": str(confirmation.token)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Email confirmed."

    user.refresh_from_db()
    confirmation.refresh_from_db()

    assert user.is_active is True
    assert confirmation.is_confirmed is True


@pytest.mark.django_db
def test_confirm_email_invalid(api_client):
    url = reverse("apps.accounts:confirm-email")

    response = api_client.post(
        url,
        {"token": "00000000-0000-0000-0000-000000000000"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Invalid or expired token"


@pytest.mark.django_db
def test_confirm_email_expired(api_client):
    confirmation = EmailConfirmationFactory()
    confirmation.expires_at = timezone.now() - timedelta(days=1)
    confirmation.save()

    url = reverse("apps.accounts:confirm-email")

    response = api_client.post(
        url,
        {"token": str(confirmation.token)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Invalid or expired token"

    confirmation.refresh_from_db()
    assert confirmation.is_confirmed is False


@pytest.mark.django_db
def test_logout_success(api_client, user):
    api_client.force_authenticate(user=user)

    refresh = RefreshToken.for_user(user)

    url = reverse("apps.accounts:logout")

    response = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Logged out successfully"

    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()


@pytest.mark.django_db
def test_logout_invalid_token(api_client, user):
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:logout")

    response = api_client.post(
        url,
        {"refresh": "invalid"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Invalid token"


@pytest.mark.django_db
def test_logout_refresh_cannot_be_reused(api_client, user):
    api_client.force_authenticate(user=user)

    refresh = RefreshToken.for_user(user)

    url = reverse("apps.accounts:logout")

    # logout -> blacklist token
    response = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    # try reuse same refresh
    response_reuse = api_client.post(
        reverse("apps.accounts:token_refresh"),
        {"refresh": str(refresh)},
        format="json",
    )

    assert response_reuse.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_refresh_token_rotation(api_client, user):
    user.is_active = True
    user.set_password("StrongPass123")
    user.save()

    refresh = RefreshToken.for_user(user)

    url = reverse("apps.accounts:token_refresh")

    response1 = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response1.status_code == status.HTTP_200_OK
    assert "access" in response1.data

    new_refresh = response1.data.get("refresh")

    # old refresh must be invalid after rotation
    response2 = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response2.status_code == status.HTTP_401_UNAUTHORIZED

    # new refresh should work
    response3 = api_client.post(
        url,
        {"refresh": new_refresh},
        format="json",
    )

    assert response3.status_code == status.HTTP_200_OK
    assert "access" in response3.data


@pytest.mark.django_db
def test_login_updates_last_login(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = True
    user.last_login = None
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": user.email, "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()
    assert user.last_login is not None


@pytest.mark.django_db
def test_logout_invalidates_refresh_token_only(api_client, user):
    user.is_active = True
    user.save()

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    url = reverse("apps.accounts:logout")

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    # access still valid (expected behavior)
    protected_url = reverse("apps.accounts:me")

    response_check = api_client.get(protected_url)

    assert response_check.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_refresh_rotation_blacklists_old_token(api_client, user):
    user.is_active = True
    user.save()

    refresh = RefreshToken.for_user(user)

    url = reverse("apps.accounts:token_refresh")

    response1 = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response1.status_code == status.HTTP_200_OK

    # old refresh must be invalid after rotation
    response2 = api_client.post(
        url,
        {"refresh": str(refresh)},
        format="json",
    )

    assert response2.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_400_BAD_REQUEST,
    )


@pytest.mark.django_db
def test_failed_login_does_not_change_user_state(api_client, user):
    user.is_active = True
    user.last_login = None
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    user.refresh_from_db()
    assert user.last_login is None
    assert user.is_active is True


@pytest.mark.django_db
def test_login_not_found_has_no_side_effects(api_client):
    url = reverse("apps.accounts:login")

    response = api_client.post(
        url,
        {"email": "missing@test.com", "password": "123"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # just ensure no user was created accidentally
    assert User.objects.filter(email="missing@test.com").exists() is False


@pytest.mark.django_db
def test_login_blocked_user(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = True
    user.is_blocked = True
    user.save()

    url = reverse("apps.accounts:login")
    response = api_client.post(
        url,
        {"email": user.email, "password": "StrongPass123"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["errors"]["detail"] == "This account has been blocked."
