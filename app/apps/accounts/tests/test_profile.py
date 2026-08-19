# app/apps/accounts/tests/test_profile.py
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status


def generate_test_image():
    file = BytesIO()

    image = Image.new("RGB", (100, 100))
    image.save(file, "jpeg")
    file.seek(0)

    return SimpleUploadedFile(
        "avatar.jpg",
        file.read(),
        content_type="image/jpeg",
    )


@pytest.mark.django_db
def test_get_profile(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["first_name"] == user.first_name
    assert response.data["last_name"] == user.last_name


@pytest.mark.django_db
def test_patch_profile(api_client, user):

    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.patch(url, {"first_name": "Updated"}, format="json")
    user.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Updated"
    assert user.first_name == "Updated"


@pytest.mark.django_db
def test_get_profile_unauthorized(api_client):
    url = reverse("apps.accounts:profile")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_put_profile(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.put(
        url,
        {
            "first_name": "Full",
            "last_name": "Update",
        },
        format="json",
    )

    user.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Full"
    assert response.data["last_name"] == "Update"

    assert user.first_name == "Full"
    assert user.last_name == "Update"


@pytest.mark.django_db
def test_patch_profile_empty_name(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.patch(url, {"first_name": ""}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "This field may not be blank." in response.data["errors"]["first_name"]
    assert "first_name" in response.data["errors"]


@pytest.mark.django_db
def test_upload_avatar(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("apps.accounts:profile"),
        {"avatar": generate_test_image()},
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.avatar.name


@pytest.mark.django_db
def test_avatar_too_large(api_client, user):
    api_client.force_authenticate(user=user)

    file = SimpleUploadedFile(
        "big.jpg",
        b"x" * (5 * 1024 * 1024 + 1),
        content_type="image/jpeg",
    )

    response = api_client.patch(
        reverse("apps.accounts:profile"),
        {"avatar": file},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "avatar" in response.data["errors"]


@pytest.mark.django_db
def test_avatar_invalid_type(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    file = SimpleUploadedFile("file.txt", b"not_image", content_type="text/plain")

    response = api_client.patch(url, {"avatar": file}, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "avatar" in response.data["errors"]


@pytest.mark.django_db
def test_profile_returns_current_user(api_client, user):

    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == user.id
    assert response.data["email"] == user.email


@pytest.mark.django_db
def test_profile_cannot_override_user_id(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("apps.accounts:profile"),
        {
            "id": 999,
            "first_name": "Hacked",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.first_name == "Hacked"


@pytest.mark.django_db
def test_profile_cannot_change_email(api_client, user):
    api_client.force_authenticate(user=user)

    old_email = user.email

    response = api_client.patch(
        reverse("apps.accounts:profile"),
        {
            "email": "hacker@test.com",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.email == old_email


@pytest.mark.django_db
def test_profile_cannot_modify_is_staff(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("apps.accounts:profile")

    response = api_client.patch(url, {"is_staff": True}, format="json")

    user.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK
    assert user.is_staff is False


@pytest.mark.django_db
def test_update_profile_changes_password_with_correct_current_password(
    api_client, user
):
    user.set_password("OldPass123!")
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile")
    response = api_client.patch(
        url,
        {"current_password": "OldPass123!", "new_password": "NewSecurePass456!"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("NewSecurePass456!")


@pytest.mark.django_db
def test_update_profile_rejects_wrong_current_password(api_client, user):
    user.set_password("OldPass123!")
    user.save()
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile")
    response = api_client.patch(
        url,
        {"current_password": "WrongPass", "new_password": "NewSecurePass456!"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "current_password" in response.data["errors"]


@pytest.mark.django_db
def test_update_profile_rejects_new_password_without_current(api_client, user):
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile")
    response = api_client.patch(
        url,
        {"new_password": "NewSecurePass456!"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "current_password" in response.data["errors"]


@pytest.mark.django_db
def test_update_profile_without_password_still_updates_name(api_client, user):
    api_client.force_authenticate(user=user)

    url = reverse("apps.accounts:profile")
    response = api_client.patch(
        url,
        {"first_name": "NewName"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.first_name == "NewName"
