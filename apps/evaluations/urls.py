from django.urls import path

from .views import experiment_results_view

app_name = "evaluations"

urlpatterns = [
    path("", experiment_results_view, name="results"),
]

