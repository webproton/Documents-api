"""
Celery configuration module.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    "auto-expire-requests-every-day": {
        "task": "app.apps.documents.tasks.auto_expire_document_requests_task",
        "schedule": crontab(hour=0, minute=0),  # Every midnight
    },
}
