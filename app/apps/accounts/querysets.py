# app/apps/accounts/querysets.py
from django.db import models
from django.utils import timezone


class UserDeviceQuerySet(models.QuerySet):
    """Custom queryset for UserDevice with reusable domain shortcuts."""

    def active(self):
        """Non-revoked, non-expired devices ordered by last login."""
        return self.filter(
            is_revoked=False,
            expires_at__gt=timezone.now(),
        ).order_by("-last_login_at")

    def revoke_all_except(self, raw_token: str | None = None) -> int:
        """
        Bulk-revoke all active/non-revoked devices, optionally keeping the one
        identified by raw_token (current session).

        Returns the number of revoked devices.
        """
        qs = self.filter(is_revoked=False)
        if raw_token:
            qs = qs.exclude(device_token_hash=self.model.hash_token(raw_token))
        return qs.update(is_revoked=True)
