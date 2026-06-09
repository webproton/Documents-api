from rest_framework import serializers

from app.apps.notifications.models import Notification


class NotificationListSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying a list of notifications.
    Eliminates the heavy `message` field (HTML body).
    """

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "type",
            "type_display",
            "status",
            "status_display",
            "recipient_email",
            "created",
            "sent_at",
        ]
        #
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """
    serializer for viewing a specific notification (Detail View).
    Includes the HTML content of the email.
    """

    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Notification

        fields = [
            "id",
            "title",
            # HTML-field
            "message",
            "type",
            "type_display",
            "status",
            "status_display",
            "recipient_email",
            "user",
            "document",
            "created",
            "modified",
            "sent_at",
        ]
        read_only_fields = fields
