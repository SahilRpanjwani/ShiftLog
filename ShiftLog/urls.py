from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda request: redirect("dashboard:dashboard"), name="home"),
    path("dashboard/", include("dashboard.urls")),
    path("documents/", include("documents.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)