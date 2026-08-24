from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.shortcuts import render

from app.apps.billing.services.stripe import StripeService, StripeServiceError

from .forms import ChangePlanActionForm
from .models import EmailConfirmation, SocialAccount, User


@admin.action(description="Block selected users")
def block_users(modeladmin, request, queryset):
    """Block selected users, preventing them from logging in."""

    updated = queryset.update(is_blocked=True)
    modeladmin.message_user(request, f"{updated} user(s) blocked.", messages.SUCCESS)


@admin.action(description="Unblock selected users")
def unblock_users(modeladmin, request, queryset):
    """Unblock selected users, restoring their ability to log in."""

    updated = queryset.update(is_blocked=False)
    modeladmin.message_user(request, f"{updated} user(s) unblocked.", messages.SUCCESS)


@admin.action(description="Cancel subscription for selected users")
def cancel_subscription_action(modeladmin, request, queryset):
    """Cancel the Stripe subscription for selected users, moving them back to FREE."""

    success_count = 0
    skipped_users = []

    for user in queryset.select_related("subscription"):
        # Skip users without an active paid Stripe subscription.
        subscription = getattr(user, "subscription", None)

        if subscription is None or not subscription.stripe_subscription_id:
            skipped_users.append(f"{user.email} (no active paid subscription)")
            continue
        # Cancel the subscription in Stripe and schedule cancellation
        # at the end of the current billing period.
        StripeService.cancel_subscription(subscription)
        success_count += 1

    if success_count:
        modeladmin.message_user(
            request,
            f"Subscription cancellation scheduled for {success_count} user(s).",
            messages.SUCCESS,
        )
    if skipped_users:
        # Report users that could not be processed instead of failing
        # the whole bulk action.
        modeladmin.message_user(
            request,
            f"Skipped: {', '.join(skipped_users)}",
            messages.WARNING,
        )


@admin.action(description="Change plan for selected users")
def change_plan_action(modeladmin, request, queryset):
    """
    Change the subscription plan for selected users.

    Users with an active Stripe subscription are updated via
    StripeService.change_plan(), which keeps Stripe in sync. Users
    without a Stripe subscription (e.g. still on FREE) are updated
    locally, since there is nothing to synchronize with Stripe.
    """
    # The first request displays the plan selection form.
    # The second request contains the selected plan and applies the action.
    if "apply" in request.POST:
        form = ChangePlanActionForm(request.POST)
        if form.is_valid():
            new_plan = form.cleaned_data["plan"]
            success_count = 0
            failed_users = []

            for user in queryset.select_related("subscription"):
                subscription = getattr(user, "subscription", None)

                # A user must have a subscription record to change its plan.
                if subscription is None:
                    failed_users.append(f"{user.email} (no subscription)")
                    continue

                # Nothing to change if the user is already on the selected plan
                if subscription.plan_id == new_plan.id:
                    success_count += 1
                    continue

                if not subscription.stripe_subscription_id:
                    # No Stripe subscription exists, so only the local plan
                    # needs to be changed.
                    subscription.plan = new_plan
                    subscription.save(update_fields=["plan"])
                    success_count += 1
                    continue

                try:
                    # Keep the local subscription and Stripe subscription
                    # synchronized for users with an active Stripe subscription.
                    StripeService.change_plan(subscription, new_plan)
                    success_count += 1
                except StripeServiceError as exc:
                    failed_users.append(f"{user.email} ({exc})")

            if success_count:
                modeladmin.message_user(
                    request,
                    f"Plan updated for {success_count} user(s).",
                    messages.SUCCESS,
                )
            if failed_users:
                modeladmin.message_user(
                    request,
                    f"Failed for: {', '.join(failed_users)}",
                    messages.WARNING,
                )
            return None
    else:
        # Preserve the selected users when opening the intermediate
        # plan selection form in Django Admin.
        form = ChangePlanActionForm(
            initial={
                "_selected_action": queryset.values_list("pk", flat=True),
            }
        )

    return render(
        request,
        "admin/accounts/change_plan_action.html",
        context={
            "users": queryset,
            "form": form,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """add user field  to admin dashboard"""

    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_blocked",
        "registration_method",
        "current_plan",
    )
    list_filter = ("is_active", "is_blocked", "registration_method")
    search_fields = ("email", "first_name", "last_name")
    actions = [
        block_users,
        unblock_users,
        change_plan_action,
        cancel_subscription_action,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("subscription__plan")

    def current_plan(self, obj):
        subscription = getattr(obj, "subscription", None)
        if subscription is None or subscription.plan is None:
            return "—"
        return subscription.plan.get_name_display()

    current_plan.short_description = "Plan"


@admin.register(EmailConfirmation)
class EmailConfirmationAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "is_confirmed")
    search_fields = ("user__email", "token")


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "provider_user_id", "created_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "provider_user_id")
