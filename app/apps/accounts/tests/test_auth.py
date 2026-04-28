from datetime import timedelta

import pytest
from apps.accounts.tests.factories import EmailConfirmationFactory, User
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from app.apps.accounts.serializers import LoginSerializer, RegisterSerializer
from app.apps.accounts.services import confirm_email


@pytest.mark.django_db
def test_register_user(api_client):
    url = reverse("apps.accounts:register")

    data = {"email": "test@test.com", "password": "StrongPass123"}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 201
    assert response.data["status"] == "confirmation_required"


@pytest.mark.django_db
def test_duplicate_email(api_client, user):
    url = reverse("apps.accounts:register")

    data = {"email": user.email, "password": "StrongPass123"}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_email_confirmation_is_expired():
    confirmation = EmailConfirmationFactory()

    confirmation.expires_at = timezone.now() - timedelta(days=1)
    confirmation.save()

    assert confirmation.is_expired() is True


@pytest.mark.django_db
def test_login_success(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = True
    user.save()

    url = reverse("apps.accounts:login")

    data = {"email": user.email, "password": "StrongPass123"}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_login_not_confirmed(api_client, user):
    user.set_password("StrongPass123")
    user.is_active = False
    user.save()

    url = reverse("apps.accounts:login")

    data = {"email": user.email, "password": "StrongPass123"}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_confirm_email_success(api_client):
    confirmation = EmailConfirmationFactory()

    url = reverse("apps.accounts:confirm-email")

    data = {"token": str(confirmation.token)}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 200


@pytest.mark.django_db
def test_confirm_email_invalid(api_client):
    url = reverse("apps.accounts:confirm-email")

    data = {"token": "00000000-0000-0000-0000-000000000000"}

    response = api_client.post(url, data, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_logout_invalid_token(api_client, user):
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:logout")

    response = api_client.post(url, {"refresh": "invalid"}, format="json")

    assert response.status_code == 400
    assert "error" in response.data


@pytest.mark.django_db
def test_login_wrong_password(api_client, user):
    user.set_password("123")
    user.is_active = True
    user.save()

    url = reverse("apps.accounts:login")

    response = api_client.post(
        url, {"email": user.email, "password": "wrong"}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_logout_success(api_client, user):
    api_client.force_authenticate(user=user)

    refresh = RefreshToken.for_user(user)

    url = reverse("apps.accounts:logout")

    response = api_client.post(url, {"refresh": str(refresh)}, format="json")

    assert response.status_code == 200
    assert response.data["message"] == "Logged out successfully"


@pytest.mark.django_db
def test_confirm_email_with_none():
    """
    Проверяем ранний выход, если confirmation = None
    """

    # вызываем сервис с пустым значением
    result = confirm_email(None)

    # проверяем, что функция корректно завершилась
    assert result is None


@pytest.mark.django_db
def test_confirm_email_user_already_active():
    """
    Если пользователь уже активен — функция ничего не делает
    и просто возвращает confirmation.
    """

    # 1. создаём confirmation через фабрику
    confirmation = EmailConfirmationFactory()

    # 2. делаем пользователя уже активным
    confirmation.user.is_active = True
    confirmation.user.save()

    # 3. вызываем сервис
    result = confirm_email(confirmation)

    # 4. проверяем, что вернулся тот же confirmation
    assert result == confirmation

    # 5. проверяем, что confirmation НЕ пометился как подтверждённый
    assert confirmation.is_confirmed is False

    # 6. проверяем, что пользователь остался активным
    assert confirmation.user.is_active is True


@pytest.mark.django_db
def test_login_user_not_active():
    User.objects.create_user(
        email="test@test.com",
        password="StrongPass123",
        is_active=False,
    )

    serializer = LoginSerializer(
        data={"email": "test@test.com", "password": "StrongPass123"}
    )

    assert serializer.is_valid() is False
    assert "Email is not confirmed" in str(serializer.errors)


@pytest.mark.django_db
def test_register_duplicate_email(api_client, user):
    url = reverse("apps.accounts:register")

    response = api_client.post(
        url, {"email": user.email, "password": "StrongPass123"}, format="json"
    )

    assert response.status_code == 400
    assert response.data["email"][0].code == "unique"


@pytest.mark.django_db
def test_register_password_too_similar_to_email():
    serializer = RegisterSerializer(
        data={"email": "test@test.com", "password": "test@test.com123"}
    )

    assert serializer.is_valid() is False
    assert "Password too similar to email" in str(serializer.errors)


@pytest.mark.django_db
def test_login_user_not_found(api_client):
    url = reverse("apps.accounts:login")

    response = api_client.post(
        url, {"email": "notexists@test.com", "password": "StrongPass123"}, format="json"
    )

    assert response.status_code == 400
    assert "Invalid credentials" in str(response.data)
