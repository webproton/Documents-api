# app/apps/accounts/tests/test_utils.py
from unittest.mock import MagicMock, patch

from django.conf import settings

from app.apps.accounts import utils


class TestUtilsAndSMSService:

    def test_generate_otp_code(self):
        """Verify generated OTP is 6 digits long by default."""
        code = utils.generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_hash_otp_code_deterministic(self):
        """Verify HMAC SHA-256 hash is deterministic for same input."""
        code = "123456"
        hash1 = utils.hash_otp_code(code)
        hash2 = utils.hash_otp_code(code)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_get_client_ip_from_x_forwarded_for(self):
        """Verify IP parsing prioritizes X-Forwarded-For proxy header."""
        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.195, 70.41.3.18, 150.172.238.178",
            "REMOTE_ADDR": "10.0.0.1",
        }
        assert utils.get_client_ip(request) == "203.0.113.195"

    def test_get_client_ip_fallback_remote_addr(self):
        """Verify IP parsing falls back to REMOTE_ADDR if no proxy header exists."""
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "198.51.100.1"}
        assert utils.get_client_ip(request) == "198.51.100.1"

    def test_parse_user_agent(self):
        """Verify user agent parsing into browser and OS string."""
        request = MagicMock()
        request.META = {
            "HTTP_USER_AGENT": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
            )
        }
        parsed = utils.parse_user_agent(request)
        assert "Chrome" in parsed
        assert "Mac OS X" in parsed

    @patch("app.apps.accounts.utils.logger")
    def test_sms_service_debug_mode(self, mock_logger):
        """Verify SMS service logs code to console without API call in DEBUG mode."""
        with patch.object(settings, "DEBUG", True):
            res = utils.SMSService.send_otp("+380970000000", "654321")
            assert res is True
            mock_logger.info.assert_called_once()
            assert "654321" in mock_logger.info.call_args[0][0]

    @patch("app.apps.accounts.utils.Client")
    def test_sms_service_production_twilio_success(self, mock_twilio_client):
        """Verify SMS service calls Twilio API when DEBUG is False."""
        mock_instance = MagicMock()
        mock_instance.messages.create.return_value.sid = "SM123456789"
        mock_twilio_client.return_value = mock_instance

        with (
            patch.object(settings, "DEBUG", False),
            patch.object(settings, "TWILIO_ACCOUNT_SID", "AC_TEST"),
            patch.object(settings, "TWILIO_AUTH_TOKEN", "AUTH_TEST"),
            patch.object(settings, "TWILIO_PHONE_NUMBER", "+12025550143"),
        ):

            res = utils.SMSService.send_otp("+380970000000", "123456")

            assert res is True
            mock_instance.messages.create.assert_called_once_with(
                body="Your verification code is: 123456",
                from_="+12025550143",
                to="+380970000000",
            )
