from django.conf import settings
from django.db import models

from apps.catalog.models import Book


class OfflineJobRun(models.Model):
    job_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    processed_user_count = models.PositiveIntegerField(default=0)
    summary = models.TextField(blank=True)


class RecommendationResult(models.Model):
    STRATEGY_CHOICES = [("hot", "Hot"), ("itemcf", "ItemCF"), ("usercf", "UserCF"), ("hybrid", "Hybrid")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    generated_at = models.DateTimeField()
    top_k = models.PositiveIntegerField(default=20)


class RecommendationItem(models.Model):
    result = models.ForeignKey(RecommendationResult, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    rank = models.PositiveIntegerField()
    score = models.FloatField(default=0.0)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["rank"]


class SimilarBookResult(models.Model):
    source_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="similarity_source")
    target_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="similarity_target")
    score = models.FloatField()
    rank = models.PositiveIntegerField()

    class Meta:
        ordering = ["rank"]
