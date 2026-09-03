# app/apps/accounts/tests/test_redis_manager.py
import hmac

import pytest
from django.core.cache import cache

from app.apps.accounts import utils
from app.apps.accounts.redis_manager import TwoFactorRedisManager
from app.apps.accounts.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def clear_redis_cache():
    """Ensure clean cache state before and after every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestTwoFactorRedisManager:

    def test_create_2fa_session_success(self):
        """Verify session creation returns
        valid token/code and sets Redis keys correctly.
        """
        user = UserFactory()
        token, code = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        assert isinstance(token, str)
        assert len(code) == 6
        assert code.isdigit()

        session_data = TwoFactorRedisManager.get_session(token)
        assert session_data is not None
        assert session_data["user_id"] == user.id
        assert session_data["method"] == "EMAIL"
        assert hmac.compare_digest(session_data["otp_hash"], utils.hash_otp_code(code))

        assert TwoFactorRedisManager.is_resend_on_cooldown(user.id) is True

    def test_verify_otp_code_success(self):
        """Verify successful code validation
        invalidates the session and returns user_id.
        """
        user = UserFactory()
        token, code = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        is_valid, user_id, err_msg = TwoFactorRedisManager.verify_otp_code(token, code)

        assert is_valid is True
        assert user_id == user.id
        assert err_msg == ""
        assert TwoFactorRedisManager.get_session(token) is None

    def test_verify_otp_code_invalid_attempt_increment(self):
        """Verify failed attempt increments counter
        and calculates remaining attempts.
        """
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        is_valid, user_id, err_msg = TwoFactorRedisManager.verify_otp_code(
            token, "000000"
        )

        assert is_valid is False
        assert user_id is None
        assert "2 attempt(s) remaining" in err_msg

    def test_verify_otp_code_max_attempts_exceeded(self):
        """Verify session is invalidated when maximum attempt limit (3) is reached."""
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        TwoFactorRedisManager.verify_otp_code(token, "111111")
        TwoFactorRedisManager.verify_otp_code(token, "222222")
        is_valid, user_id, err_msg = TwoFactorRedisManager.verify_otp_code(
            token, "333333"
        )

        assert is_valid is False
        assert user_id is None
        assert "Maximum 2FA verification attempts exceeded" in err_msg
        assert TwoFactorRedisManager.get_session(token) is None

    def test_resend_2fa_code_cooldown_blocking(self):
        """Verify code resend request fails when cooldown is active."""
        user = UserFactory()
        token, _ = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        success, new_code, user_id, method, err_msg = (
            TwoFactorRedisManager.resend_2fa_code(token)
        )

        assert success is False
        assert new_code is None
        assert "Please wait before requesting" in err_msg

    def test_resend_2fa_code_success_after_cooldown(self):
        """Verify code resend succeeds after cooldown key expires/clears."""
        user = UserFactory()
        token, old_code = TwoFactorRedisManager.create_2fa_session(
            user.id, method="EMAIL"
        )

        cooldown_key = f"{TwoFactorRedisManager.RESEND_COOLDOWN_PREFIX}:{user.id}"
        cache.delete(cooldown_key)

        success, new_code, user_id, method, err_msg = (
            TwoFactorRedisManager.resend_2fa_code(token)
        )

        assert success is True
        assert new_code != old_code
        assert len(new_code) == 6
        assert user_id == user.id
        assert method == "EMAIL"
        assert err_msg == ""

    def test_invalidate_all_user_sessions(self):
        """Verify all active 2FA sessions for a user
        across different devices are deleted atomically.
        """
        user = UserFactory()
        token1, _ = TwoFactorRedisManager.create_2fa_session(user.id, method="EMAIL")

        # Reset the cooldown to create a second session
        # for the same user (simulation of the 2nd device)
        cache.delete(f"{TwoFactorRedisManager.RESEND_COOLDOWN_PREFIX}:{user.id}")
        token2, _ = TwoFactorRedisManager.create_2fa_session(user.id, method="SMS")

        # Both sessions must be active
        assert TwoFactorRedisManager.get_session(token1) is not None
        assert TwoFactorRedisManager.get_session(token2) is not None

        # Recall all user sessions
        TwoFactorRedisManager.invalidate_all_user_sessions(user.id)

        # Both sessions have been removed from Redis
        assert TwoFactorRedisManager.get_session(token1) is None
        assert TwoFactorRedisManager.get_session(token2) is None
