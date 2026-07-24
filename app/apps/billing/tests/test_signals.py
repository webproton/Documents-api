# apps/billing/tests/test_signals.py

import pytest

from app.apps.accounts.tests.factories import UserFactory
from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory


@pytest.mark.django_db
def test_user_gets_free_subscription_after_registration():
    free_plan = PlanFactory(name=Plan.NAME.FREE)

    user = UserFactory()

    subscription = Subscription.objects.get(user=user)

    assert subscription.plan == free_plan
    assert subscription.status == Subscription.STATUS.ACTIVE
