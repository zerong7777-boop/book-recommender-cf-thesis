from django.urls import path

from .views import dashboard_home_view, trigger_rebuild_view

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home_view, name="home"),
    path("trigger-rebuild/", trigger_rebuild_view, name="trigger_rebuild"),
]
