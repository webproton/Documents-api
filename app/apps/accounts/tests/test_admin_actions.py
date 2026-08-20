# app/apps/accounts/tests/test_admin_actions.py

from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from app.apps.accounts.admin import (
    UserAdmin,
    block_users,
    cancel_subscription_action,
    change_plan_action,
    unblock_users,
)
from app.apps.accounts.forms import ChangePlanActionForm
from app.apps.accounts.tests.factories import UserFactory
from app.apps.billing.models import Plan, Subscription
from app.apps.billing.services.stripe import StripeServiceError
from app.apps.billing.tests.factories.plan import PlanFactory


def _set_subscription(user, **fields):
    Subscription.objects.filter(user=user).update(**fields)
    user.refresh_from_db()
    return user.subscription


@pytest.fixture
def admin_instance():
    from app.apps.accounts.models import User

    return UserAdmin(model=User, admin_site=AdminSite())


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.mark.django_db
class TestBlockUnblockActions:
    def test_block_users_sets_is_blocked_true_for_all_selected(
        self, admin_instance, request_factory
    ):
        user1 = UserFactory(is_active=True)
        user2 = UserFactory(is_active=True)
        request = request_factory.post("/admin/accounts/user/")
        request._messages = (
            []
        )  # message_user needs a messages backend; use client instead if this fails

        from django.contrib.auth.models import User as DjangoUser  # noqa
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        queryset = type(user1).objects.filter(pk__in=[user1.pk, user2.pk])

        block_users(admin_instance, request, queryset)

        user1.refresh_from_db()
        user2.refresh_from_db()

        assert user1.is_blocked is True
        assert user2.is_blocked is True

    def test_unblock_users_sets_is_blocked_false(self, admin_instance, request_factory):
        user1 = UserFactory(is_active=True, is_blocked=True)
        user2 = UserFactory(is_active=True, is_blocked=True)

        request = request_factory.post("/admin/accounts/user/")
        setattr(request, "session", "session")
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user1).objects.filter(pk__in=[user1.pk, user2.pk])

        unblock_users(admin_instance, request, queryset)

        user1.refresh_from_db()
        user2.refresh_from_db()

        assert user1.is_blocked is False
        assert user2.is_blocked is False


@pytest.mark.django_db
class TestChangePlanActionForm:
    def test_form_excludes_free_plan_from_choices(self):
        form = ChangePlanActionForm()
        plan_names = list(form.fields["plan"].queryset.values_list("name", flat=True))
        assert Plan.NAME.FREE not in plan_names


@pytest.mark.django_db
class TestChangePlanAction:
    def test_change_plan_updates_locally_when_no_stripe_subscription(
        self, admin_instance, request_factory
    ):
        pro_plan = PlanFactory(name=Plan.NAME.PRO, is_active=True)
        business_plan = PlanFactory(name=Plan.NAME.BUSINESS, is_active=True)

        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            plan=pro_plan,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id=None,
        )

        request = request_factory.post(
            "/admin/accounts/user/",
            data={
                "apply": "1",
                "plan": business_plan.id,
                "_selected_action": str(user.pk),
            },
        )
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        change_plan_action(admin_instance, request, queryset)

        subscription = Subscription.objects.get(user=user)
        assert subscription.plan == business_plan

    def test_change_plan_calls_stripe_service_when_subscription_exists(
        self, admin_instance, request_factory
    ):
        pro_plan = PlanFactory(name=Plan.NAME.PRO)
        business_plan = PlanFactory(name=Plan.NAME.BUSINESS)

        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            plan=pro_plan,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id="sub_123",
        )

        request = request_factory.post(
            "/admin/accounts/user/",
            data={
                "apply": "1",
                "plan": business_plan.id,
                "_selected_action": str(user.pk),
            },
        )
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        with patch(
            "app.apps.accounts.admin.StripeService.change_plan"
        ) as mock_change_plan:
            change_plan_action(admin_instance, request, queryset)

        mock_change_plan.assert_called_once()

    def test_change_plan_skips_user_already_on_target_plan(
        self, admin_instance, request_factory
    ):
        pro_plan = PlanFactory(name=Plan.NAME.PRO)

        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            plan=pro_plan,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id="sub_123",
        )

        request = request_factory.post(
            "/admin/accounts/user/",
            data={"apply": "1", "plan": pro_plan.id, "_selected_action": str(user.pk)},
        )
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        with patch(
            "app.apps.accounts.admin.StripeService.change_plan"
        ) as mock_change_plan:
            change_plan_action(admin_instance, request, queryset)

        mock_change_plan.assert_not_called()

    def test_change_plan_reports_stripe_failure(self, admin_instance, request_factory):
        pro_plan = PlanFactory(name=Plan.NAME.PRO)
        business_plan = PlanFactory(name=Plan.NAME.BUSINESS)

        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            plan=pro_plan,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id="sub_123",
        )

        request = request_factory.post(
            "/admin/accounts/user/",
            data={
                "apply": "1",
                "plan": business_plan.id,
                "_selected_action": str(user.pk),
            },
        )
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        with patch(
            "app.apps.accounts.admin.StripeService.change_plan",
            side_effect=StripeServiceError("boom"),
        ):
            # should not raise — failure is caught and reported
            change_plan_action(admin_instance, request, queryset)

        subscription = Subscription.objects.get(user=user)
        assert subscription.plan == pro_plan  # unchanged


@pytest.mark.django_db
class TestCancelSubscriptionAction:
    def test_cancels_subscription_for_paid_user(self, admin_instance, request_factory):
        pro_plan = PlanFactory(name=Plan.NAME.PRO)
        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            plan=pro_plan,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id="sub_123",
        )

        request = request_factory.post("/admin/accounts/user/")
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        with patch(
            "app.apps.accounts.admin.StripeService.cancel_subscription"
        ) as mock_cancel:
            cancel_subscription_action(admin_instance, request, queryset)

        mock_cancel.assert_called_once()

    def test_skips_user_without_active_subscription(
        self, admin_instance, request_factory
    ):
        user = UserFactory(is_active=True)
        _set_subscription(
            user,
            status=Subscription.STATUS.ACTIVE,
            stripe_subscription_id=None,
        )

        request = request_factory.post("/admin/accounts/user/")
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        queryset = type(user).objects.filter(pk=user.pk)

        with patch(
            "app.apps.accounts.admin.StripeService.cancel_subscription"
        ) as mock_cancel:
            cancel_subscription_action(admin_instance, request, queryset)

        mock_cancel.assert_not_called()


@pytest.mark.django_db
class TestCurrentPlanDisplay:
    def test_shows_plan_name_when_subscription_exists(self):
        pro_plan = PlanFactory(name=Plan.NAME.PRO)
        user = UserFactory(is_active=True)
        _set_subscription(user, plan=pro_plan)

        admin_instance = UserAdmin(model=type(user), admin_site=AdminSite())
        result = admin_instance.current_plan(user)

        assert result == pro_plan.get_name_display()

    def test_shows_dash_when_no_subscription(self):
        from app.apps.accounts.models import User

        admin_instance = UserAdmin(model=User, admin_site=AdminSite())
        user = UserFactory(is_active=True)
        Subscription.objects.filter(user=user).delete()
        user.refresh_from_db()

        result = admin_instance.current_plan(user)

        assert result == "—"
