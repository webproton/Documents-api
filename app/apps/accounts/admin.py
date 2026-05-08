from django.contrib import admin

from .models import EmailConfirmation, User


class UserAdmin(admin.ModelAdmin):
    """add user field  to admin dashboard"""

    list_display = ("id", "email", "first_name", "last_name")


admin.site.register(User, UserAdmin)


@admin.register(EmailConfirmation)
class EmailConfirmationAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "is_confirmed")
    search_fields = ("user__email", "token")
