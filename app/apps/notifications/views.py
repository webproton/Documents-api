import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from app.apps.notifications.models import Notification
from app.apps.notifications.serializers import (
    NotificationListSerializer,
    NotificationSerializer,
)


class NotificationFilter(django_filters.FilterSet):
    """
    Custom filter for notifications regarding technical specifications.
    Allows you to filter by exact status, type, and creation date range.
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created", lookup_expr="lte"
    )

    class Meta:
        model = Notification
        fields = ["status", "type"]


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
        An administrator (is_staff) sees absolutely all notifications in the system.
        """
        user = self.request.user
        if user.is_staff:
            return Notification.objects.all().select_related("user", "document")

        return Notification.objects.filter(user=user).select_related("document")

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        return NotificationSerializer
