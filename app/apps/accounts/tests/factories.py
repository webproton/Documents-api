# app/apps/accounts/tests/factories.py
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from app.apps.accounts.models import EmailConfirmation, SocialAccount

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
    is_active = False

    class Params:
        with_avatar = factory.Trait(
            avatar=factory.django.ImageField(filename="avatar.jpg"),
        )
        blocked = factory.Trait(
            is_blocked=True,
        )


class EmailConfirmationFactory(factory.django.DjangoModelFactory):
    """
    Factory for email confirmation tokens.
    """

    class Meta:
        model = EmailConfirmation

    user = factory.SubFactory(UserFactory)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    is_confirmed = False


class SocialAccountFactory(factory.django.DjangoModelFactory):
    """Factory for creating social accounts."""

    class Meta:
        model = SocialAccount

    user = factory.SubFactory(UserFactory)
    provider = SocialAccount.PROVIDER.GOOGLE
    provider_user_id = factory.Sequence(lambda n: f"google-user-{n}")
