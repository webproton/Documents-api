import django_filters

from app.apps.notifications.models import Notification


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
