from decimal import Decimal

import factory
from billing.models import Transaction
from billing.tests.factories.order import OrderFactory
from django.conf import settings


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    order = factory.SubFactory(OrderFactory)

    type = Transaction.TYPE.PAYMENT
    status = Transaction.STATUS.SUCCESS

    amount = Decimal("19.99")
    currency = settings.DEFAULT_CURRENCY

    stripe_event_id = factory.Sequence(lambda n: f"evt_{n}")
    event_type = "checkout.session.completed"

    raw_payload = factory.LazyFunction(dict)
