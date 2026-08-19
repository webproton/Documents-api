from django.contrib import admin

from .models import EmailConfirmation, SocialAccount, User


class UserAdmin(admin.ModelAdmin):
    """add user field  to admin dashboard"""

    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_blocked",
        "registration_method",
    )
    list_filter = ("is_active", "is_blocked", "registration_method")
    search_fields = ("email", "first_name", "last_name")


admin.site.register(User, UserAdmin)


@admin.register(EmailConfirmation)
class EmailConfirmationAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "is_confirmed")
    search_fields = ("user__email", "token")


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "provider_user_id", "created_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "provider_user_id")
