from decimal import Decimal

import factory
from billing.models import Order
from billing.tests.factories.subscription import SubscriptionFactory
from django.conf import settings


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    subscription = factory.SubFactory(SubscriptionFactory)
    user = factory.SelfAttribute("subscription.user")
    plan = factory.SelfAttribute("subscription.plan")

    amount = Decimal("19.99")
    currency = settings.DEFAULT_CURRENCY
    status = Order.STATUS.PENDING

    stripe_checkout_session_id = factory.Sequence(lambda n: f"cs_{n}")
    stripe_payment_intent_id = factory.Sequence(lambda n: f"pi_{n}")
    stripe_invoice_id = factory.Sequence(lambda n: f"in_{n}")
    stripe_customer_id = factory.Sequence(lambda n: f"cus_{n}")

    metadata = factory.LazyFunction(dict)
