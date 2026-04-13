from django.conf import settings
from django.shortcuts import render

from .services import load_experiment_summary


def experiment_results_view(request):
    return render(
        request,
        "evaluations/experiment_results.html",
        {"summary": load_experiment_summary(settings.BASE_DIR)},
    )
