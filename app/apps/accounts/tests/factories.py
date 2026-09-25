# app/apps/accounts/tests/factories.py
import secrets
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from app.apps.accounts import utils
from app.apps.accounts.models import (
    EmailConfirmation,
    PhoneConfirmation,
    SocialAccount,
    UserDevice,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """
    Factory for creating test users.
    """

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    first_name = "Test"
    last_name = "User"
    is_active = True
    is_blocked = False

    phone_number = None
    phone_confirmed = False

    class Params:
        with_avatar = factory.Trait(
            avatar=factory.django.ImageField(filename="avatar.jpg"),
        )
        blocked = factory.Trait(
            is_blocked=True,
        )
        with_phone = factory.Trait(
            phone_number=factory.Sequence(lambda n: f"+38097{n:07d}"),
            phone_confirmed=False,
        )
        phone_confirmed_user = factory.Trait(
            phone_number=factory.Sequence(lambda n: f"+38097{n:07d}"),
            phone_confirmed=True,
        )


class EmailConfirmationFactory(factory.django.DjangoModelFactory):
    """
    Factory for email confirmation tokens.
    """

    class Meta:
        model = EmailConfirmation

    user = factory.SubFactory(UserFactory, is_active=False)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    is_confirmed = False


class SocialAccountFactory(factory.django.DjangoModelFactory):
    """Factory for creating social accounts."""

    class Meta:
        model = SocialAccount

    user = factory.SubFactory(UserFactory)
    provider = SocialAccount.PROVIDER.GOOGLE
    provider_user_id = factory.Sequence(lambda n: f"google-user-{n}")


class PhoneConfirmationFactory(factory.django.DjangoModelFactory):
    """
    Factory for phone confirmation tokens and codes.
    """

    class Meta:
        model = PhoneConfirmation

    user = factory.SubFactory(UserFactory)
    phone_number = factory.Sequence(lambda n: f"+38097{n:07d}")
    code_hash = factory.LazyFunction(lambda: utils.hash_otp_code("123456"))
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))
    is_confirmed = False


class UserDeviceFactory(factory.django.DjangoModelFactory):
    """
    Factory for trusted user devices (Remember Me feature).
    """

    class Meta:
        model = UserDevice

    user = factory.SubFactory(UserFactory)
    device_token_hash = factory.LazyFunction(
        lambda: UserDevice.hash_token(secrets.token_urlsafe(32))
    )
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/118.0.0.0 Safari/537.36"
    )
    ip_address = "192.168.1.1"
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=60))
    is_revoked = False

    class Params:
        # Allows passing a raw_token directly when overriding the hash
        raw_token = factory.Trait(
            device_token_hash=factory.LazyAttribute(
                lambda o: UserDevice.hash_token(o.raw_token_value)
            )
        )
