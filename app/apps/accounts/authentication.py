from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class SafeJWTAuthentication(JWTAuthentication):
    """
    Authenticate JWT users and reject inactive or blocked accounts.
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

        return user, token
