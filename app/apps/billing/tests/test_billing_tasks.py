import pytest
from django.utils import timezone

from app.apps.billing.models import Subscription
from app.apps.billing.tasks import expire_subscriptions
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


@pytest.mark.django_db
def test_expire_subscriptions():
    subscription = SubscriptionFactory(
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
        current_period_end=timezone.now() - timezone.timedelta(minutes=1),
    )

    expire_subscriptions()

    subscription.refresh_from_db()

    assert subscription.status == Subscription.STATUS.EXPIRED
    assert subscription.end_date is not None


@pytest.mark.django_db
def test_expire_subscriptions_keeps_active_subscription():
    subscription = SubscriptionFactory(
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
        current_period_end=timezone.now() + timezone.timedelta(days=1),
    )

    expire_subscriptions()

    subscription.refresh_from_db()

    assert subscription.status == Subscription.STATUS.ACTIVE
    assert subscription.end_date is None


@pytest.mark.django_db
def test_expire_subscriptions_ignores_non_canceling_subscription():
    subscription = SubscriptionFactory(
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=False,
        current_period_end=timezone.now() - timezone.timedelta(days=1),
    )

    expire_subscriptions()

    subscription.refresh_from_db()

    assert subscription.status == Subscription.STATUS.ACTIVE
