# app/apps/accounts/redis_manager.py
import hmac
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from .utils import generate_otp_code, hash_otp_code

logger = logging.getLogger(__name__)


class TwoFactorRedisManager:
    """
    Manages 2FA temporary sessions, OTP codes,
    attempt counters, and cooldowns in Redis.
    """

    PRE_AUTH_PREFIX = "2fa_pre_auth"
    RESEND_COOLDOWN_PREFIX = "2fa_cooldown"
    ACTIVE_TOKENS_PREFIX = "2fa_active_tokens"
    ATTEMPTS_PREFIX = "2fa_attempts"

    # Default fallback values mapped directly to settings.py
    SESSION_TTL = getattr(settings, "PRE_AUTH_TOKEN_LIFETIME", 1200)
    MAX_ATTEMPTS = getattr(settings, "TWO_FACTOR_MAX_ATTEMPTS", 3)
    RESEND_COOLDOWN = getattr(settings, "TWO_FACTOR_RESEND_COOLDOWN", 60)

    @classmethod
    def _redis_client(cls):
        """Raw django-redis client — needed for atomic commands
        (INCR/SADD/SREM/EXPIRE) that the generic Django cache API
        doesn't expose."""
        return cache.client.get_client(write=True)

    @classmethod
    def generate_otp_code(cls) -> str:
        """
        Generates a secure 6-digit numeric OTP string.
        """
        return generate_otp_code()

    @classmethod
    def generate_pre_auth_token(cls) -> str:
        """
        Generates a unique URL-safe UUID4
        string for pre-authentication sessions.
        """
        return str(uuid.uuid4())

    @classmethod
    def create_2fa_session(cls, user_id: int, method: str) -> Tuple[str, str]:
        """
        Creates a new 2FA session in Redis with OTP code,
        user context, and attempt tracking.
        Returns a tuple of (pre_auth_token, raw_otp_code).
        """
        # Generate unique pre-auth token and secure 6-digit OTP code
        pre_auth_token = cls.generate_pre_auth_token()
        raw_code = generate_otp_code()
        otp_hash = hash_otp_code(raw_code)

        cache_key = f"{cls.PRE_AUTH_PREFIX}:{pre_auth_token}"
        session_data = {
            "user_id": user_id,
            "otp_hash": otp_hash,
            "method": method,
        }

        # Store session in Redis with 20 minutes TTL
        cache.set(cache_key, session_data, timeout=cls.SESSION_TTL)

        # Track active session under user ID for bulk revocation support
        cls._track_token_for_user(user_id, pre_auth_token, cls.SESSION_TTL)
        # Set resend cooldown to prevent spamming SMS/Email (60 seconds)
        cls._set_cooldown(user_id)

        return pre_auth_token, raw_code

    @classmethod
    def resend_2fa_code(
        cls, pre_auth_token: str
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str], str]:
        """
        Generates a new OTP code for an existing active pre_auth session,
        resets failed attempts, and sets a new resend cooldown.

        Returns:
            Tuple[is_success, new_otp_code, user_id, error_message]
        """
        cache_key = f"{cls.PRE_AUTH_PREFIX}:{pre_auth_token}"
        session_data = cache.get(cache_key)

        # Reject request if pre-auth session does not exist or has expired
        if not session_data:
            return (
                False,
                None,
                None,
                None,
                "Invalid or expired 2FA session. Please log in again.",
            )
        user_id = session_data["user_id"]
        delivery_method = session_data.get("method")

        # Check if user is currently rate-limited by resend cooldown
        if cls.is_resend_on_cooldown(user_id):
            return (
                False,
                None,
                user_id,
                delivery_method,
                "Please wait before requesting a new verification code.",
            )

        # Generate new OTP code and replace old hash in session payload
        new_otp_code = cls.generate_otp_code()
        session_data["otp_hash"] = hash_otp_code(new_otp_code)

        # Update session payload in Redis with fresh TTL
        cache.set(cache_key, session_data, timeout=cls.SESSION_TTL)

        # Reset failed verification attempt counter for the regenerated code
        cls._redis_client().delete(f"{cls.ATTEMPTS_PREFIX}:{pre_auth_token}")

        # Update resend cooldown and refresh active token tracking TTL
        cls._set_cooldown(user_id)
        cls._track_token_for_user(user_id, pre_auth_token, cls.SESSION_TTL)

        return True, new_otp_code, user_id, delivery_method, ""

    @classmethod
    def is_resend_on_cooldown(cls, user_id: int) -> bool:
        """
        Checks if the user is currently on
        cooldown for requesting a new OTP.
        """
        cooldown_key = f"{cls.RESEND_COOLDOWN_PREFIX}:{user_id}"
        return cache.get(cooldown_key) is not None

    @classmethod
    def _set_cooldown(cls, user_id: int) -> None:
        """Internal helper to set resend cooldown in Redis."""
        cooldown_key = f"{cls.RESEND_COOLDOWN_PREFIX}:{user_id}"
        # Default cooldown: 60 seconds
        cache.set(cooldown_key, True, timeout=cls.RESEND_COOLDOWN)

    @classmethod
    def get_session(cls, pre_auth_token: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves active 2FA session payload from Redis.
        """
        cache_key = f"{cls.PRE_AUTH_PREFIX}:{pre_auth_token}"
        return cache.get(cache_key)

    @classmethod
    def verify_otp_code(
        cls, pre_auth_token: str, input_code: str
    ) -> Tuple[bool, Optional[int], str]:
        """
        Verifies input code against the stored OTP hash.

        Attempt counting uses an atomic Redis INCR on a dedicated key,
        not a field on session_data — this makes it safe under
        concurrent requests (parallel/retried submissions can't
        undercount attempts, see services.py docstring).
        """
        cache_key = f"{cls.PRE_AUTH_PREFIX}:{pre_auth_token}"
        session_data = cache.get(cache_key)

        if not session_data:
            return False, None, "Invalid or expired 2FA session. Please log in again."

        user_id = session_data["user_id"]
        clean_code = (input_code or "").strip()

        # Constant-time comparison prevents timing attack vulnerability
        if hmac.compare_digest(hash_otp_code(clean_code), session_data["otp_hash"]):
            cls.invalidate_session(pre_auth_token)
            return True, user_id, ""

        # Atomic increment prevents race conditions
        # during concurrent request submissions
        attempts_key = f"{cls.ATTEMPTS_PREFIX}:{pre_auth_token}"
        redis_client = cls._redis_client()

        # Atomic INCR ensures race-condition safety on concurrent requests
        attempts = redis_client.incr(attempts_key)

        # Set expiry on first failed attempt to prevent
        # orphaned counter keys in Redis
        if attempts == 1:
            # the first increment for this key is to set the TTL
            # so that it doesn't live forever
            redis_client.expire(attempts_key, cls.SESSION_TTL)

        # Invalidate session immediately if maximum attempt threshold is reached
        if attempts >= cls.MAX_ATTEMPTS:
            cls.invalidate_session(pre_auth_token)
            redis_client.delete(attempts_key)
            logger.warning(
                f"2FA session {pre_auth_token} invalidated"
                "after {attempts} failed attempts."
            )
            return (
                False,
                None,
                "Maximum 2FA verification attempts exceeded. Please log in again.",
            )

        remaining_attempts = cls.MAX_ATTEMPTS - attempts
        return (
            False,
            None,
            f"Invalid verification code. {remaining_attempts} attempt(s) remaining.",
        )

    @classmethod
    def invalidate_session(
        cls, pre_auth_token: str, user_id: int | None = None
    ) -> None:
        """
        Manually deletes a 2FA session key, attempts counter,
        and cleans up user tracking in Redis.
        """
        redis_client = cls._redis_client()
        cache_key = f"{cls.PRE_AUTH_PREFIX}:{pre_auth_token}"

        # Retrieve user_id from session payload if not explicitly provided
        if user_id is None:
            session_data = cache.get(cache_key)
            if isinstance(session_data, dict):
                user_id = session_data.get("user_id")

        # Remove token from user tracking set if user_id is known
        if user_id is not None:
            cls._untrack_token_for_user(user_id, pre_auth_token)

        # Remove session data and atomic attempt counter keys
        cache.delete(cache_key)
        redis_client.delete(f"{cls.ATTEMPTS_PREFIX}:{pre_auth_token}")

    @classmethod
    def _track_token_for_user(cls, user_id: int, token: str, ttl: int) -> None:
        """Remember this pre_auth_token as belonging to user_id, so we can
        find and invalidate it later without scanning all Redis keys."""
        key = f"{cls.ACTIVE_TOKENS_PREFIX}:{user_id}"
        redis_client = cls._redis_client()
        # Using pipeline: add a token and update the TTL in 1 network request
        pipe = redis_client.pipeline()
        pipe.sadd(key, token)
        pipe.expire(key, ttl)
        pipe.execute()

    @classmethod
    def _untrack_token_for_user(cls, user_id: int, token: str) -> None:
        """Remove a single pre_auth_token from user tracking list."""
        key = f"{cls.ACTIVE_TOKENS_PREFIX}:{user_id}"
        cls._redis_client().srem(key, token)

    @classmethod
    def invalidate_all_user_sessions(cls, user_id: int) -> None:
        key = f"{cls.ACTIVE_TOKENS_PREFIX}:{user_id}"
        redis_client = cls._redis_client()

        # Retrieve all active pre-auth tokens associated with the user
        tokens = redis_client.smembers(key)
        if not tokens:
            return

        # Execute bulk deletion in a single atomic network round-trip via Redis pipeline
        pipe = redis_client.pipeline()

        for raw_token in tokens:
            token = raw_token.decode() if isinstance(raw_token, bytes) else raw_token

            # Delete session data via Django cache to correctly
            # account for backend key prefixes
            cache.delete(f"{cls.PRE_AUTH_PREFIX}:{token}")

            # Queue deletion of atomic attempt counters in pipeline
            pipe.delete(f"{cls.ATTEMPTS_PREFIX}:{token}")

        # Delete active tokens tracking set and user resend cooldown
        pipe.delete(key)
        pipe.delete(f"{cls.RESEND_COOLDOWN_PREFIX}:{user_id}")
        pipe.execute()
