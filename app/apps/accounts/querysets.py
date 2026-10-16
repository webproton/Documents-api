# app/apps/accounts/querysets.py
from django.db import models
from django.utils import timezone


class UserDeviceQuerySet(models.QuerySet):
    """Custom queryset for UserDevice with reusable domain shortcuts."""

    def active(self):
        """Devices to show the user: a live session or a still-trusted
        device (signed out, but skips 2FA), newest login first."""
        now = timezone.now()
        return (
            self.filter(is_revoked=False)
            .filter(models.Q(expires_at__gt=now) | models.Q(trusted_until__gt=now))
            .order_by("-last_login_at")
        )

    def revoke_all_except(self, raw_token: str | None = None) -> int:
        """
        Bulk-revoke all active/non-revoked devices, optionally keeping the one
        identified by raw_token (current session).

        Returns the number of revoked devices.
        """
        qs = self.filter(is_revoked=False)
        if raw_token:
            qs = qs.exclude(device_token_hash=self.model.hash_token(raw_token))
        return qs.update(is_revoked=True, trusted_until=None)

    def live(self):
        """Sessions that can still be used: not revoked, not expired."""
        return self.filter(is_revoked=False, expires_at__gt=timezone.now())

    def is_live_session(self, user_id: int, device_id: int) -> bool:
        """Whether a JWT's device_id still points to an active session."""
        return self.live().filter(id=device_id, user_id=user_id).exists()
