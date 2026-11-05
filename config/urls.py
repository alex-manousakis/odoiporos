from django.contrib import admin
from django.urls import include, path
from core.dashboard import DashboardLoginView

urlpatterns = [
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
    path("accounts/login/", DashboardLoginView.as_view(), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
]
