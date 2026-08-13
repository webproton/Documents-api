# app/apps/billing/admin.py

from django.contrib import admin

from app.apps.billing.models import Order, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "document_limit",
        "is_active",
        "stripe_price_id",
        "created",
    )
    list_filter = ("is_active", "name")
    search_fields = ("name", "stripe_price_id")
    ordering = ("price",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "current_period_end",
        "cancel_at_period_end",
        "created",
    )
    list_filter = ("status", "plan", "cancel_at_period_end")
    search_fields = ("user__email", "stripe_subscription_id", "stripe_customer_id")

    readonly_fields = (
        "stripe_subscription_id",
        "stripe_customer_id",
        "current_period_end",
        "created",
        "modified",
    )

    fields = (
        "user",
        "plan",
        "status",
        "start_date",
        "end_date",
        "cancel_at_period_end",
        "stripe_subscription_id",
        "stripe_customer_id",
        "current_period_end",
        "created",
        "modified",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "plan",
        "amount",
        "currency",
        "status",
        "stripe_invoice_id",
        "created",
    )
    list_filter = ("status", "currency", "plan")
    search_fields = (
        "user__email",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "stripe_invoice_id",
        "stripe_customer_id",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
