# billing/urls.py

from django.urls import path

from app.apps.billing.views import CheckoutView, CurrentSubscriptionView, PlanViewSet

app_name = "apps.billing"

urlpatterns = [
    path(
        "plans/",
        PlanViewSet.as_view({"get": "list"}),
        name="plan-list",
    ),
    path(
        "subscription/",
        CurrentSubscriptionView.as_view(),
        name="current-subscription",
    ),
    path(
        "checkout/",
        CheckoutView.as_view(),
        name="checkout",
    ),
]
