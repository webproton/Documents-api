from rest_framework.routers import SimpleRouter

from app.apps.notifications.views import NotificationViewSet

app_name = "apps.notifications"

router = SimpleRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = router.urls
