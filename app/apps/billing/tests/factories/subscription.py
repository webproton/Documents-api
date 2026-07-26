import factory
from django.utils import timezone

from app.apps.accounts.tests.factories import UserFactory
from app.apps.billing.models import Subscription
from app.apps.billing.tests.factories.plan import PlanFactory


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(PlanFactory)
    status = Subscription.STATUS.ACTIVE
    start_date = factory.LazyFunction(timezone.now)
    current_period_end = factory.LazyFunction(
        lambda: timezone.now() + timezone.timedelta(days=30)
    )
    cancel_at_period_end = False
    stripe_subscription_id = factory.Sequence(lambda n: f"sub_{n}")
    stripe_customer_id = factory.Sequence(lambda n: f"cus_{n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = kwargs["user"]

        subscription = Subscription.objects.filter(user=user).first()

        if subscription:
            for key, value in kwargs.items():
                setattr(subscription, key, value)
            subscription.save()
            return subscription

        return super()._create(model_class, *args, **kwargs)
