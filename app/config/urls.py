"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Documents API",
        default_version="v1",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("app.apps.accounts.urls")),
    path(
        "api/documents/",
        include("app.apps.documents.urls", namespace="app.apps.documents"),
    ),
    path(
        "api/notifications/",
        include("app.apps.notifications.urls", namespace="notifications"),
    ),
    path(
        "api/billing/", include("app.apps.billing.urls", namespace="app.apps.billing")
    ),
    re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0)),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0)),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
