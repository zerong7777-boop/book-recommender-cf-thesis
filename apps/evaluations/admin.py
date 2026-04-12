from django.contrib import admin

from apps.evaluations.models import EvaluationRun


@admin.register(EvaluationRun)
class EvaluationRunAdmin(admin.ModelAdmin):
    list_display = ("experiment_name", "strategy", "dataset_name", "started_at", "finished_at")
    list_filter = ("strategy", "dataset_name")
    search_fields = ("experiment_name", "dataset_name")
