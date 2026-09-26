from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class TwoFactorConfirmRateThrottle(AnonRateThrottle):
    """Limits 2FA OTP verification attempts per IP to prevent brute-force attacks."""

    scope = "2fa_confirm"


class TwoFactorResendRateThrottle(AnonRateThrottle):
    """Limits 2FA OTP resend requests per IP to prevent spam and gateway abuse."""

    scope = "2fa_resend"


class PhoneConfirmationRateThrottle(UserRateThrottle):
    """Limits SMS confirmation requests per authenticated user to control costs."""

    scope = "phone_confirm_send"
