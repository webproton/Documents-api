# app/apps/billing/tests/test_expire_subscriptions_task.py
from datetime import timedelta

import pytest
from django.utils import timezone

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tasks import expire_subscriptions
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.billing.tests.factories.subscription import SubscriptionFactory


@pytest.mark.django_db
def test_expire_subscriptions_expires_past_period_end():
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    subscription = SubscriptionFactory(
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
        current_period_end=timezone.now() - timedelta(days=1),
    )

    expire_subscriptions()

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS.EXPIRED
    assert subscription.plan == Plan.objects.get(name=Plan.NAME.FREE)
    assert subscription.end_date is not None


@pytest.mark.django_db
def test_expire_subscriptions_ignores_without_cancel_flag():
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    subscription = SubscriptionFactory(
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=False,
        current_period_end=timezone.now() - timedelta(days=1),
    )

    expire_subscriptions()

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS.ACTIVE
    assert subscription.plan == pro_plan


@pytest.mark.django_db
def test_expire_subscriptions_ignores_period_not_ended():
    pro_plan = PlanFactory(name=Plan.NAME.PRO)
    subscription = SubscriptionFactory(
        plan=pro_plan,
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
        current_period_end=timezone.now() + timedelta(days=5),
    )

    expire_subscriptions()

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS.ACTIVE


@pytest.mark.django_db
def test_expire_subscriptions_ignores_already_expired():
    SubscriptionFactory(
        plan=PlanFactory(name=Plan.NAME.PRO),
        status=Subscription.STATUS.EXPIRED,
        cancel_at_period_end=True,
        current_period_end=timezone.now() - timedelta(days=1),
    )

    result = expire_subscriptions()

    assert result == 0
