# test_plan_api.py
import pytest
from django.urls import reverse
from rest_framework import status

from app.apps.billing.models import Plan
from app.apps.billing.tests.factories.plan import PlanFactory


@pytest.mark.django_db
def test_plan_list_returns_only_active_plans(api_client):
    PlanFactory(name=Plan.NAME.FREE, is_active=True)
    PlanFactory(name=Plan.NAME.PRO, is_active=True)
    PlanFactory(name=Plan.NAME.BUSINESS, is_active=False)

    response = api_client.get(reverse("app.apps.billing:plan-list"))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_plan_list_is_ordered_by_price(api_client):
    PlanFactory(name=Plan.NAME.BUSINESS, price=30)
    PlanFactory(name=Plan.NAME.FREE, price=0)
    PlanFactory(name=Plan.NAME.PRO, price=10)

    response = api_client.get(reverse("app.apps.billing:plan-list"))

    prices = [plan["price"] for plan in response.data]

    assert prices == ["0.00", "10.00", "30.00"]


@pytest.mark.django_db
def test_plan_list_returns_expected_fields(api_client):
    PlanFactory()

    response = api_client.get(reverse("app.apps.billing:plan-list"))

    assert set(response.data[0].keys()) == {
        "id",
        "name",
        "description",
        "document_limit",
        "price",
    }


@pytest.mark.django_db
def test_plan_list_is_public(api_client):
    response = api_client.get(reverse("app.apps.billing:plan-list"))

    assert response.status_code == status.HTTP_200_OK
