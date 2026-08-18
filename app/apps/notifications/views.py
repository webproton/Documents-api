from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from app.apps.notifications.filters import NotificationFilter
from app.apps.notifications.models import Notification
from app.apps.notifications.serializers import (
    NotificationListSerializer,
    NotificationSerializer,
)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing notifications for the current user.
    Supports only GET requests (list and retrieve).
    """

    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = NotificationFilter

    # Allowed fields for sorting by spec. (?ordering=-created)
    ordering_fields = ["created", "sent_at"]
    ordering = ["-created"]  # default: new ones first

    def get_queryset(self):
        """
        We guarantee data security: a regular user sees only THEIR notifications.
        """
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user).select_related(
            "document"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        return NotificationSerializer
