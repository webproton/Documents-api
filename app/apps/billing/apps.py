from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "app.apps.billing"
    default_auto_field = "django.db.models.BigAutoField"
    label = "billing"

    def ready(self):
        import app.apps.billing.signals  # noqa: F401
