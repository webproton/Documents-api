from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

# Absolute path on purpose: this module is loaded via settings as
# "apps.accounts.authentication", while the app is registered as
# "app.apps.accounts" — a relative import would load models twice.
from app.apps.accounts.models import UserDevice
from app.apps.accounts.services import DEVICE_ID_CLAIM


class SafeJWTAuthentication(JWTAuthentication):
    """
    Authenticate JWT users and reject inactive or blocked accounts,
    and access tokens whose device session was revoked or ended.
    """

    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            return None

        user, token = result

        if not user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        if user.is_blocked:
            raise AuthenticationFailed("This account has been blocked.")

        # Tokens issued before sessions existed have no claim and still work
        device_id = token.get(DEVICE_ID_CLAIM)
        if device_id is not None and not UserDevice.objects.is_live_session(
            user.id, device_id
        ):
            raise AuthenticationFailed("This session has been ended.")

        return user, token
