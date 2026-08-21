# app/apps/accounts/permissions.py

from rest_framework.permissions import IsAuthenticated


class IsActiveAndNotBlocked(IsAuthenticated):
    """
    Extends IsAuthenticated to also reject requests from users whose
    account is inactive (unconfirmed email) or blocked by an admin.

    Checked on every authenticated request, not just at login — so
    blocking a user takes effect immediately for any still-valid
    access token, without needing to blacklist every outstanding
    access token individually.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        return request.user.is_active and not request.user.is_blocked
