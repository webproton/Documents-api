# app/apps/billing/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from app.apps.accounts.models import User
from app.apps.billing.models import Plan, Subscription


@receiver(post_save, sender=User)
def create_free_subscription(sender, instance, created, **kwargs):
    if not created:
        return

    if Subscription.objects.filter(user=instance).exists():
        return

    free_plan = Plan.objects.get(name=Plan.NAME.FREE)

    Subscription.objects.create(
        user=instance,
        plan=free_plan,
        status=Subscription.STATUS.ACTIVE,
    )
