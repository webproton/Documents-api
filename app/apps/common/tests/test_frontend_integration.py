"""Settings that let the React frontend talk to the API from a browser."""

import pytest
from django.urls import reverse

FRONTEND_ORIGIN = "http://frontend.test"


@pytest.fixture
def cors_origin(settings):
    settings.CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN]


@pytest.mark.django_db
@pytest.mark.usefixtures("cors_origin")
def test_cors_preflight_allows_frontend_with_device_token(api_client):
    response = api_client.options(
        reverse("apps.accounts:login"),
        HTTP_ORIGIN=FRONTEND_ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, x-device-token",
    )

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    allowed_headers = response.headers["access-control-allow-headers"]
    assert "x-device-token" in allowed_headers
    assert "authorization" in allowed_headers


@pytest.mark.django_db
@pytest.mark.usefixtures("cors_origin")
def test_cors_rejects_unknown_origin(api_client):
    response = api_client.get(
        reverse("app.apps.billing:plan-list"), HTTP_ORIGIN="http://evil.test"
    )

    assert "access-control-allow-origin" not in response.headers


def test_stripe_redirects_point_to_frontend(settings):
    assert settings.STRIPE_SUCCESS_URL == f"{settings.FRONTEND_URL}/billing/success"
    assert settings.STRIPE_CANCEL_URL == f"{settings.FRONTEND_URL}/billing/cancel"
