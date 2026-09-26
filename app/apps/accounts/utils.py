import hashlib
import hmac
import logging
import secrets
import string

import user_agents
from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2, GeoIP2Exception
from twilio.rest import Client

logger = logging.getLogger(__name__)


class SMSService:
    """
    Service wrapper for sending SMS verification codes via Twilio API.
    Supports debug logging fallback when running in development mode.
    """

    @staticmethod
    def send_otp(phone_number: str, code: str) -> bool:
        """
        Sends OTP code via Twilio in Production or logs it to console in Debug mode.
        """
        # Print OTP to console in development mode instead of sending actual SMS
        if getattr(settings, "DEBUG", False):
            logger.info(f"[DEV 2FA MOCK] OTP for {phone_number} is: {code}")
            return True

        # Fetch required Twilio credentials from configuration
        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        from_number = getattr(settings, "TWILIO_PHONE_NUMBER", None)

        # Abort if any required Twilio setting is missing
        if not all([account_sid, auth_token, from_number]):
            logger.error("Twilio credentials are missing in settings.")
            return False
        # Attempt to dispatch SMS message through Twilio Client
        try:
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=f"Your verification code is: {code}",
                from_=from_number,
                to=phone_number,
            )
            return bool(message.sid)
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio to {phone_number}: {e}")
            return False


def get_client_ip(request) -> str:
    """
    Extracts the client's real IP address from HTTP headers.
    Handles proxy headers like X-Forwarded-For.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    # Use first IP in header if request passed through a reverse proxy
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    # Fallback to direct client connection IP
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip


def parse_user_agent(request) -> str:
    """
    Parses the raw User-Agent header into a human-readable string.
    Example output: 'Chrome 118 on macOS'
    """
    user_agent_str = request.META.get("HTTP_USER_AGENT", "")
    # Fallback if request has no User-Agent header
    if not user_agent_str:
        return "Unknown Device"

    ua = user_agents.parse(user_agent_str)
    browser = ua.browser.family
    os = ua.os.family

    return f"{browser} on {os}"


def get_geoip_location(ip_address: str) -> str:
    """
    Resolves IP address to 'City, Country' using MaxMind GeoLite2 database.
    Returns 'Unknown' on failure or if IP is local/internal.
    """
    # Skip lookup for missing or loopback IP addresses
    if not ip_address or ip_address in ("127.0.0.1", "localhost", "::1"):
        return "Local Network"

    # Query GeoIP database for city and country information
    try:
        g = GeoIP2()
        city_info = g.city(ip_address)
        city = city_info.get("city")
        country = city_info.get("country_name")
        # Prefer full 'City, Country' string if both exist
        if city and country:
            return f"{city}, {country}"
        return country or city or "Unknown Location"
    except (GeoIP2Exception, Exception) as e:
        logger.debug(f"GeoIP resolution failed for IP {ip_address}: {e}")
        return "Unknown"


def generate_otp_code(length: int = 6) -> str:
    """Generates a cryptographically secure numeric OTP string."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_otp_code(code: str) -> str:
    return hmac.new(
        key=settings.OTP_HASH_SECRET.encode(),
        msg=code.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
