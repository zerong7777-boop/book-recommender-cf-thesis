from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import MaxValueValidator, MinValueValidator

from apps.catalog.models import Book


class UserRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="user_ratings")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    rated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="unique_user_book_rating"),
            models.CheckConstraint(condition=Q(score__gte=1) & Q(score__lte=5), name="user_rating_score_1_5"),
        ]


class UserRatingHistory(models.Model):
    ACTION_CHOICES = [("create", "Create"), ("update", "Update"), ("delete", "Delete")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rating_history")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="rating_history")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=5),
                name="user_rating_history_score_1_5",
            ),
        ]


class ImportedInteraction(models.Model):
    dataset_name = models.CharField(max_length=100, default="goodbooks-10k")
    dataset_user_id = models.PositiveIntegerField()
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="imported_interactions")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset_name", "dataset_user_id", "book"],
                name="unique_imported_interaction_dataset_user_book",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=5),
                name="imported_interaction_score_1_5",
            ),
        ]
