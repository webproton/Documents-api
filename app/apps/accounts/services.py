# app/apps/accounts/services.py
"""Shared login flow for password and social (Google) authentication."""

from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserDevice
from .redis_manager import TwoFactorRedisManager
from .tasks import send_email_otp_task, send_sms_task
from .utils import extract_raw_device_token

# JWT claim linking access/refresh tokens to their UserDevice session
DEVICE_ID_CLAIM = "device_id"


def get_trusted_device(user, request):
    """Return the user's device that may skip 2FA (trusted and not revoked)
    matching the device token sent with the request, or None."""
    raw_token = extract_raw_device_token(request)
    if not raw_token:
        return None

    return UserDevice.objects.filter(
        user=user,
        device_token_hash=UserDevice.hash_token(raw_token),
        is_revoked=False,
        trusted_until__gt=timezone.now(),
    ).first()


def issue_session_tokens(user, request, *, trust_device=False) -> dict:
    """
    Final step of every successful login (password, Google, 2FA):
    start/refresh the device session and mint JWTs bound to it.

    The device_token must be stored by the client and sent back as
    X-Device-Token: it identifies the session (and skips 2FA if trusted).
    """
    device, raw_device_token = UserDevice.issue(user, request, trusted=trust_device)

    refresh = RefreshToken.for_user(user)
    # Copied into the access token and kept on refresh rotation
    refresh[DEVICE_ID_CLAIM] = device.id
    update_last_login(None, user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "email": user.email,
        "id": user.id,
        "device_token": raw_device_token,
    }


def start_2fa_session(user) -> dict:
    """Create a 2FA session and send the OTP via the user's chosen method."""
    try:
        pre_auth_token, otp_code = TwoFactorRedisManager.create_2fa_session(
            user_id=user.id,
            method=user.two_factor_method,
        )
    except ValueError as exc:
        # A code was sent less than TWO_FACTOR_RESEND_COOLDOWN seconds
        # ago (e.g. quick re-login after failed 2FA) → 429, not 500
        raise Throttled(detail=str(exc)) from exc

    # Sending OTP via Celery (separately SMS / Email) after the DB commit
    if user.two_factor_method == User.TWO_FACTOR_METHOD.SMS and user.phone_number:
        transaction.on_commit(lambda: send_sms_task.delay(user.phone_number, otp_code))
        message = "Verification code has been sent to your phone."
    else:
        transaction.on_commit(lambda: send_email_otp_task.delay(user.id, otp_code))
        message = "Verification code has been sent to your email."

    return {
        "requires_2fa": True,
        "pre_auth_token": pre_auth_token,
        "delivery_method": user.two_factor_method,
        "message": message,
    }


def complete_login(user, request) -> dict:
    """
    Second half of a password or Google login, after the user's identity
    is verified.

    - 2FA enabled and the device is not trusted → start a 2FA session,
      return {"requires_2fa": True, "pre_auth_token": ...} (no JWT yet).
    - Otherwise → start a device session, return JWTs + device_token
      with {"requires_2fa": False}.
    """
    if user.is_2fa_enabled and get_trusted_device(user, request) is None:
        return start_2fa_session(user)

    return {**issue_session_tokens(user, request), "requires_2fa": False}
