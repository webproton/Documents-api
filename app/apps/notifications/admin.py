from django.contrib import admin

from app.apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "user",
        "recipient_email",
        "document",
        "status",
        "type",
        "sent_at",
        "created",
    ]

    list_filter = ["status", "type", "created"]

    search_fields = ["title", "recipient_email", "user__email", "user__username"]

    readonly_fields = ["created", "modified", "status_changed", "sent_at"]

    raw_id_fields = ["user", "document"]
