from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/",   admin.site.urls),
    path("challan/", include("apps.challans.urls",  namespace="challans")),
    path("reports/", include("apps.reports.urls",   namespace="reports")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)