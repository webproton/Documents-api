# billing/tasks.py
from celery import shared_task
from django.utils import timezone

from app.apps.billing.models import Plan, Subscription


@shared_task
def expire_subscriptions():
    """
    Expire subscriptions whose billing period has ended.
    """
    free_plan = Plan.get_free_plan()

    return Subscription.objects.filter(
        status=Subscription.STATUS.ACTIVE,
        cancel_at_period_end=True,
        current_period_end__lte=timezone.now(),
    ).update(
        status=Subscription.STATUS.EXPIRED,
        end_date=timezone.now(),
        plan=free_plan,
    )
