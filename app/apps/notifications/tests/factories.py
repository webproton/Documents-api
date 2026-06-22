import factory
from apps.accounts.tests.factories import UserFactory

from app.apps.notifications.models import Notification


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    recipient_email = factory.LazyAttribute(lambda o: o.user.email)

    title = factory.Sequence(lambda n: f"Notification Title {n}")
    message = factory.Sequence(lambda n: f"<p>HTML Message Content {n}</p>")

    type = Notification.TYPE.EMAIL_CONFIRMATION
