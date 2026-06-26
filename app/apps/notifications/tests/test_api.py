import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.notifications.models import Notification
from app.apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


def test_unauthenticated_user_cannot_access_notifications(api_client):
    """An anonymous user should receive 401 Unauthorized"""
    url = reverse("notifications:notification-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_user_can_only_see_their_own_notifications(api_client, user, user_factory):
    """The user should not see notifications from other users."""
    other_user = user_factory()

    # create notifications for both users
    NotificationFactory(user=user, title="My Notif")
    NotificationFactory(user=other_user, title="Stranger Notif")

    api_client.force_authenticate(user=user)
    url = reverse("notifications:notification-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 1
    # We're hitting the element directly, without the "results" key.
    assert response.data[0]["title"] == "My Notif"


def test_detail_view_includes_message_field(api_client, user):
    """In the detailed view (retrieve), the message field must be present."""
    notification = NotificationFactory(user=user, message="<p>Heavy HTML content</p>")

    api_client.force_authenticate(user=user)
    url = reverse("notifications:notification-detail", kwargs={"pk": notification.id})
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "<p>Heavy HTML content</p>"


def test_api_filtering_by_status_and_type(api_client, user):
    """check that filtering the notification list by type and status works."""
    n1 = NotificationFactory(user=user, type=Notification.TYPE.EMAIL_CONFIRMATION)
    n2 = NotificationFactory(
        user=user,
        type=Notification.TYPE.REMINDER,
        status=Notification.STATUS.SENT,  # trans. status directly to the factory
    )

    api_client.force_authenticate(user=user)
    url = reverse("notifications:notification-list")

    # 1. Checking filter by (?type=EMAIL_CONFIRMATION)
    response = api_client.get(url, {"type": Notification.TYPE.EMAIL_CONFIRMATION})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == n1.id

    # 2. Checking filter by status (?status=SENT)
    response = api_client.get(url, {"status": Notification.STATUS.SENT})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == n2.id


def test_user_cannot_access_others_notification_detail(api_client, user, user_factory):
    """Пользователь не должен иметь доступ к детальному просмотру чужого уведомления."""
    other_user = user_factory()
    other_notification = NotificationFactory(user=other_user, message="Secret HTML")

    api_client.force_authenticate(user=user)
    url = reverse(
        "apps.notifications:notification-detail", kwargs={"pk": other_notification.id}
    )
    response = api_client.get(url)

    # Здесь может быть 404 Not Found (если фильтрация идет на уровне get_queryset)
    # или 403 Forbidden (если через permissions). Обычно в DRF лучше возвращать 404.
    assert response.status_code in [
        status.HTTP_404_NOT_FOUND,
        status.HTTP_403_FORBIDDEN,
    ]
