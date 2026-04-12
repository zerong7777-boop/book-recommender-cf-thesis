from django.db import models


class EvaluationRun(models.Model):
    experiment_name = models.CharField(max_length=100)
    strategy = models.CharField(max_length=20)
    dataset_name = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    metric_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return self.experiment_name
