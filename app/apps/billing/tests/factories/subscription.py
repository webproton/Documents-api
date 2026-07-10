import factory
from billing.models import Subscription
from billing.tests.factories.plan import PlanFactory
from users.tests.factories import UserFactory


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(PlanFactory)
    status = Subscription.STATUS.ACTIVE
    start_date = factory.Faker("date_time")
    current_period_end = factory.Faker("future_datetime")
    cancel_at_period_end = False
    stripe_subscription_id = factory.Sequence(lambda n: f"sub_{n}")
    stripe_customer_id = factory.Sequence(lambda n: f"cus_{n}")
