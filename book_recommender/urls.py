from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.catalog.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("ratings/", include("apps.ratings.urls")),
    path("recommendations/", include("apps.recommendations.urls")),
    path("experiments/", include("apps.evaluations.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
]

