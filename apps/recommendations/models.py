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

    def __str__(self) -> str:
        return f"{self.job_name} ({self.status})"


class RecommendationResult(models.Model):
    STRATEGY_CHOICES = [("hot", "Hot"), ("itemcf", "ItemCF"), ("usercf", "UserCF"), ("hybrid", "Hybrid")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    generated_at = models.DateTimeField()
    top_k = models.PositiveIntegerField(default=20)

    def __str__(self) -> str:
        owner = self.user_id if self.user_id is not None else "global"
        return f"{self.strategy}:{owner}:{self.generated_at.isoformat()}"


class RecommendationItem(models.Model):
    result = models.ForeignKey(RecommendationResult, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    rank = models.PositiveIntegerField()
    score = models.FloatField(default=0.0)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["result", "rank"], name="unique_recommendation_result_rank"),
            models.UniqueConstraint(fields=["result", "book"], name="unique_recommendation_result_book"),
        ]

    def __str__(self) -> str:
        return f"{self.result_id}:{self.rank}:{self.book_id}"


class SimilarBookResult(models.Model):
    source_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="similarity_source")
    target_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="similarity_target")
    score = models.FloatField()
    rank = models.PositiveIntegerField()

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["source_book", "rank"], name="unique_similar_book_source_rank"),
            models.UniqueConstraint(fields=["source_book", "target_book"], name="unique_similar_book_source_target"),
        ]

    def __str__(self) -> str:
        return f"{self.source_book_id}->{self.target_book_id} ({self.rank})"
