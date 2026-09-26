import hmac

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from app.apps.accounts import utils
from app.apps.accounts.redis_manager import TwoFactorRedisManager
from app.apps.accounts.tests.factories import UserFactory

User = get_user_model()

EMAIL = User.TWO_FACTOR_METHOD.EMAIL


@pytest.fixture(autouse=True)
def clear_redis_cache():
    """Ensure clean cache state before and after every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestTwoFactorRedisManager:

    def test_create_2fa_session_success(self):
        """Verify session creation sets session payload,
        active tokens set, and cooldown."""
        user = UserFactory()
        token, code = TwoFactorRedisManager.create_2fa_session(user.id, method=EMAIL)

        assert isinstance(token, str)
        assert len(code) == 6 and code.isdigit()

        # Check session payload
        session_data = TwoFactorRedisManager.get_session(token)
        assert session_data is not None
        assert session_data["user_id"] == user.id
        assert session_data["method"] == EMAIL
        assert hmac.compare_digest(session_data["otp_hash"], utils.hash_otp_code(code))

        # Check cooldown
        assert TwoFactorRedisManager.is_resend_on_cooldown(user.id) is True

        # Check tracking in Redis Set
        redis_client = TwoFactorRedisManager._redis_client()
        active_tokens = redis_client.smembers(
            f"{TwoFactorRedisManager.ACTIVE_TOKENS_PREFIX}:{user.id}"
        )
        decoded_tokens = {
            t.decode() if isinstance(t, bytes) else t for t in active_tokens
        }
        assert token in decoded_tokens

    def test_verify_otp_code_success_cleans_up_session(self):
        """Verify correct OTP returns user_id
        and immediately invalidates the session."""
        user = UserFactory()
        token, code = TwoFactorRedisManager.create_2fa_session(user.id, method="SMS")

        # Test with whitespace padding to ensure input normalization
        is_valid, returned_user_id, err_msg = TwoFactorRedisManager.verify_otp_code(
            token, f"  {code}  "
        )

        assert is_valid is True
        assert returned_user_id == user.id
        assert err_msg == ""
        # Session must be purged after success
        assert TwoFactorRedisManager.get_session(token) is None

    def test_verify_otp_code_invalid_session(self):
        """Verify error returned when session token is invalid or expired."""
        is_valid, user_id, err_msg = TwoFactorRedisManager.verify_otp_code(
            "non-existent-token", "123456"
        )

        assert is_valid is False
        assert user_id is None
        assert "Invalid or expired 2FA session" in err_msg

    def test_verify_otp_code_attempt_decrement_and_lockout(self):
        """Verify incremental attempt tracking and session lockout on 3rd failure."""
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method=EMAIL)

        # Attempt 1
        valid, uid, err = TwoFactorRedisManager.verify_otp_code(token, "000000")
        assert valid is False and uid is None
        assert "2 attempt(s) remaining" in err

        # Attempt 2
        valid, uid, err = TwoFactorRedisManager.verify_otp_code(token, "000000")
        assert valid is False and uid is None
        assert "1 attempt(s) remaining" in err

        # Attempt 3 (Max reached -> Invalidation)
        valid, uid, err = TwoFactorRedisManager.verify_otp_code(token, "000000")
        assert valid is False and uid is None
        assert "Maximum 2FA verification attempts exceeded" in err

        # Session must be deleted after max attempts
        assert TwoFactorRedisManager.get_session(token) is None

    def test_resend_2fa_code_blocked_by_cooldown(self):
        """Verify resend is rejected while cooldown timer is active."""
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method=EMAIL)

        success, new_code, res_uid, method, err = TwoFactorRedisManager.resend_2fa_code(
            token
        )

        assert success is False
        assert new_code is None
        assert res_uid == user.id
        assert method == EMAIL
        assert "Please wait before requesting" in err

    def test_resend_2fa_code_resets_failed_attempts(self):
        """Verify resend generates a new code
        and resets atomic failed attempts counter."""
        user = UserFactory()
        token, old_code = TwoFactorRedisManager.create_2fa_session(
            user.id, method=EMAIL
        )

        # Fail 2 attempts
        TwoFactorRedisManager.verify_otp_code(token, "000000")
        TwoFactorRedisManager.verify_otp_code(token, "000000")

        # Clear cooldown to simulate waiting 60s
        cache.delete(f"{TwoFactorRedisManager.RESEND_COOLDOWN_PREFIX}:{user.id}")

        # Resend code
        success, new_code, res_uid, method, err = TwoFactorRedisManager.resend_2fa_code(
            token
        )

        assert success is True
        assert new_code != old_code
        assert err == ""

        # Verify attempts counter was reset back to 0
        # (First bad attempt on fresh code leaves 2 attempts remaining)
        valid, _, err = TwoFactorRedisManager.verify_otp_code(token, "000000")
        assert valid is False
        assert "2 attempt(s) remaining" in err

        # Verify old code is hash-mismatched by checking session payload directly
        session = TwoFactorRedisManager.get_session(token)
        assert session["otp_hash"] != utils.hash_otp_code(old_code)
        assert session["otp_hash"] == utils.hash_otp_code(new_code)

    def test_resend_2fa_code_invalid_session(self):
        """Verify resend fails gracefully for expired/fake session."""
        success, code, uid, method, err = TwoFactorRedisManager.resend_2fa_code(
            "fake-token"
        )

        assert success is False
        assert code is None
        assert "Invalid or expired 2FA session" in err

    def test_invalidate_single_session(self):
        """Verify manually invalidating a single session
        removes tracking and attempts."""
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method=EMAIL)

        TwoFactorRedisManager.invalidate_session(token)

        assert TwoFactorRedisManager.get_session(token) is None

        # Verify token untracked from user set
        redis_client = TwoFactorRedisManager._redis_client()
        active_tokens = redis_client.smembers(
            f"{TwoFactorRedisManager.ACTIVE_TOKENS_PREFIX}:{user.id}"
        )
        assert len(active_tokens) == 0

    def test_invalidate_all_user_sessions_multi_device(self):
        """Verify revoking all user sessions purges
        multiple tokens for user A without affecting user B."""
        user_a = UserFactory()
        user_b = UserFactory()

        # User A logs in from Device 1
        token_a1, _ = TwoFactorRedisManager.create_2fa_session(user_a.id, method=EMAIL)

        # Clear cooldown to simulate User A logging in from Device 2
        cache.delete(f"{TwoFactorRedisManager.RESEND_COOLDOWN_PREFIX}:{user_a.id}")
        token_a2, _ = TwoFactorRedisManager.create_2fa_session(user_a.id, method="SMS")

        # User B logs in
        token_b1, _ = TwoFactorRedisManager.create_2fa_session(user_b.id, method=EMAIL)

        # Revoke ALL sessions for User A
        TwoFactorRedisManager.invalidate_all_user_sessions(user_a.id)

        # User A's sessions must be gone
        assert TwoFactorRedisManager.get_session(token_a1) is None
        assert TwoFactorRedisManager.get_session(token_a2) is None

        # User B's session MUST remain active and untouched
        assert TwoFactorRedisManager.get_session(token_b1) is not None
