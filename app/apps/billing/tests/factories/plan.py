# app/apps/billing/tests/factories/plan.py
from decimal import Decimal

import factory

from app.apps.billing.models import Plan


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Plan

    name = Plan.NAME.PRO
    description = factory.Faker("sentence")
    document_limit = None
    price = Decimal("19.99")
    stripe_price_id = factory.Sequence(lambda n: f"price_{n}")
    is_active = True
