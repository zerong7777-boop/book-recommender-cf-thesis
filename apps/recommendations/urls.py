from django.urls import path

from .views import recommendation_list_view

app_name = "recommendations"

urlpatterns = [
    path("", recommendation_list_view, name="list"),
]

