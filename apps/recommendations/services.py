from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from sklearn.metrics.pairwise import cosine_similarity

from apps.catalog.models import Book
from apps.ratings.models import UserRating
from apps.recommendations.cache import cache_hot_recommendations, cache_user_recommendations
from apps.recommendations.models import (
    OfflineJobRun,
    RecommendationItem,
    RecommendationResult,
    SimilarBookResult,
)


def hot_recommendations(top_k: int = 20) -> List[Book]:
    return list(Book.objects.order_by("-rating_count", "-average_rating")[:top_k])


def eligible_users():
    user_ids = (
        UserRating.objects.values("user_id")
        .annotate(rating_count=Count("id"))
        .filter(rating_count__gte=3)
        .values_list("user_id", flat=True)
    )
    return get_user_model().objects.filter(id__in=user_ids)


def _build_interaction_frame() -> pd.DataFrame:
    ratings = list(UserRating.objects.values("user_id", "book_id", "score"))
    if not ratings:
        return pd.DataFrame(columns=["user_id", "book_id", "score"])
    return pd.DataFrame.from_records(ratings)


def _build_interaction_matrix(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        return None
    return frame.pivot_table(index="user_id", columns="book_id", values="score", fill_value=0)


def _compute_item_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    similarity = cosine_similarity(matrix.T)
    return pd.DataFrame(similarity, index=matrix.columns, columns=matrix.columns)


def _itemcf_recommendations_from_similarity(
    user_id: int,
    matrix: pd.DataFrame | None,
    similarity: pd.DataFrame | None,
    top_k: int,
) -> List[Tuple[int, float]]:
    if matrix is None or similarity is None:
        return []
    if user_id not in matrix.index:
        return []
    user_ratings = matrix.loc[user_id]
    rated_mask = user_ratings.values > 0
    if rated_mask.sum() == 0:
        return []
    rated_indices = np.where(rated_mask)[0]
    scores = similarity.values[:, rated_indices].dot(user_ratings.values[rated_indices])
    scores[rated_indices] = -np.inf
    ranked_indices = np.argsort(scores)[::-1]
    recommendations: List[Tuple[int, float]] = []
    for idx in ranked_indices:
        score = scores[idx]
        if not np.isfinite(score) or score <= 0:
            continue
        book_id = int(similarity.index[idx])
        recommendations.append((book_id, float(score)))
        if len(recommendations) >= top_k:
            break
    return recommendations


def itemcf_recommendations_for_user(user_id: int, top_k: int = 20) -> List[Tuple[int, float]]:
    frame = _build_interaction_frame()
    matrix = _build_interaction_matrix(frame)
    similarity = _compute_item_similarity(matrix)
    return _itemcf_recommendations_from_similarity(user_id, matrix, similarity, top_k)


def _rebuild_similar_books(similarity: pd.DataFrame, top_k: int) -> int:
    SimilarBookResult.objects.all().delete()
    if similarity.empty:
        return 0
    results: List[SimilarBookResult] = []
    for source_id in similarity.index:
        scores = similarity.loc[source_id].drop(labels=[source_id], errors="ignore")
        scores = scores[scores > 0].sort_values(ascending=False).head(top_k)
        for rank, (target_id, score) in enumerate(scores.items(), start=1):
            results.append(
                SimilarBookResult(
                    source_book_id=int(source_id),
                    target_book_id=int(target_id),
                    score=float(score),
                    rank=rank,
                )
            )
    if results:
        SimilarBookResult.objects.bulk_create(results)
    return len(results)


def _hot_fallback_books_for_user(rated_book_ids: Iterable[int], top_k: int) -> List[Book]:
    return list(
        Book.objects.exclude(id__in=list(rated_book_ids))
        .order_by("-rating_count", "-average_rating")[:top_k]
    )


def rebuild_recommendations_for_all_users(top_k: int = 20) -> OfflineJobRun:
    now = timezone.now()
    job = OfflineJobRun.objects.create(job_name="rebuild_recommendations", status="running", started_at=now)
    processed_users = 0
    summary_parts: List[str] = []

    try:
        hot_books = hot_recommendations(top_k=top_k)
        hot_result = RecommendationResult.objects.create(
            user=None,
            strategy="hot",
            generated_at=timezone.now(),
            top_k=top_k,
        )
        hot_items = [
            RecommendationItem(
                result=hot_result,
                book=book,
                rank=rank,
                score=float(book.rating_count) + float(book.average_rating),
                reason="Popular with readers",
            )
            for rank, book in enumerate(hot_books, start=1)
        ]
        if hot_items:
            RecommendationItem.objects.bulk_create(hot_items)
        cache_hot_recommendations(hot_result)
        summary_parts.append(f"hot_items={len(hot_items)}")

        frame = _build_interaction_frame()
        matrix = _build_interaction_matrix(frame)
        similarity = _compute_item_similarity(matrix)
        if similarity is not None:
            similar_count = _rebuild_similar_books(similarity, top_k=min(top_k, 10))
            summary_parts.append(f"similar_pairs={similar_count}")

        for user in eligible_users():
            user_id = int(user.id)
            rated_book_ids = list(UserRating.objects.filter(user_id=user_id).values_list("book_id", flat=True))
            recommendations = _itemcf_recommendations_from_similarity(user_id, matrix, similarity, top_k)
            reason = "Similar to your ratings"
            if not recommendations:
                fallback_books = _hot_fallback_books_for_user(rated_book_ids, top_k=top_k)
                recommendations = [(book.id, float(book.rating_count) + float(book.average_rating)) for book in fallback_books]
                reason = "Popular fallback because ItemCF had sparse data"
            if not recommendations:
                continue
            result = RecommendationResult.objects.create(
                user_id=user_id,
                strategy="itemcf",
                generated_at=timezone.now(),
                top_k=top_k,
            )
            items = [
                RecommendationItem(
                    result=result,
                    book_id=book_id,
                    rank=rank,
                    score=score,
                    reason=reason,
                )
                for rank, (book_id, score) in enumerate(recommendations, start=1)
            ]
            RecommendationItem.objects.bulk_create(items)
            cache_user_recommendations(user_id, result)
            processed_users += 1

        job.status = "success"
        summary_parts.append(f"itemcf_users={processed_users}")
    except Exception as exc:  # pragma: no cover - failure path
        job.status = "failed"
        summary_parts.append(f"error={exc}")
        job.processed_user_count = processed_users
        job.finished_at = timezone.now()
        job.summary = "; ".join(summary_parts)
        job.save()
        raise

    job.processed_user_count = processed_users
    job.finished_at = timezone.now()
    job.summary = "; ".join(summary_parts)
    job.save()
    return job
