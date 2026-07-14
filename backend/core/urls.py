from django.contrib import admin
from django.urls import include, path

from apps.common.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("apps.tenants.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/sales/", include("apps.sales.urls")),
    path("api/voice/", include("apps.voice.urls")),
    path("api/assistant/", include("apps.assistant.urls")),
    path("django-rq/", include("django_rq.urls")),
]
