# test_checkout_serializer.py
import pytest

from app.apps.billing.models import Plan
from app.apps.billing.serializers import CheckoutSerializer
from app.apps.billing.tests.factories.plan import PlanFactory


@pytest.mark.django_db
def test_checkout_serializer_accepts_paid_plan():
    plan = PlanFactory(name=Plan.NAME.PRO)

    serializer = CheckoutSerializer(
        data={"plan": plan.id},
    )

    assert serializer.is_valid()
    assert serializer.validated_data["plan"] == plan


@pytest.mark.django_db
def test_checkout_serializer_rejects_free_plan():
    plan = PlanFactory(name=Plan.NAME.FREE)

    serializer = CheckoutSerializer(
        data={"plan": plan.id},
    )

    assert not serializer.is_valid()
    assert serializer.errors["plan"] == ["The FREE plan cannot be purchased."]


@pytest.mark.django_db
def test_checkout_serializer_rejects_inactive_plan():
    plan = PlanFactory(
        name=Plan.NAME.PRO,
        is_active=False,
    )

    serializer = CheckoutSerializer(
        data={"plan": plan.id},
    )

    assert not serializer.is_valid()
    assert "plan" in serializer.errors
