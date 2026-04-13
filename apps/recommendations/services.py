from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from sklearn.metrics.pairwise import cosine_similarity

from apps.catalog.models import Book
from apps.ratings.models import UserRating
from apps.ratings.services import build_interaction_frame, site_subject_key
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
    return build_interaction_frame()


def _build_interaction_matrix(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        return None
    return frame.pivot_table(index="subject_key", columns="book_id", values="score", fill_value=0)


def _compute_item_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    similarity = cosine_similarity(matrix.T)
    return pd.DataFrame(similarity, index=matrix.columns, columns=matrix.columns)


def _compute_user_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    similarity = cosine_similarity(matrix)
    return pd.DataFrame(similarity, index=matrix.index, columns=matrix.index)


def _itemcf_recommendations_from_similarity(
    subject_key: str,
    matrix: pd.DataFrame | None,
    similarity: pd.DataFrame | None,
    top_k: int,
) -> List[Tuple[int, float]]:
    if matrix is None or similarity is None:
        return []
    if subject_key not in matrix.index:
        return []
    user_ratings = matrix.loc[subject_key]
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


def _usercf_recommendations_from_similarity(
    subject_key: str,
    matrix: pd.DataFrame | None,
    user_similarity: pd.DataFrame | None,
    top_k: int,
) -> List[Tuple[int, float]]:
    if matrix is None or user_similarity is None:
        return []
    if subject_key not in matrix.index:
        return []

    user_ratings = matrix.loc[subject_key]
    seen_ids = {int(book_id) for book_id, value in user_ratings.items() if value > 0}
    neighbors = user_similarity.loc[subject_key].drop(labels=[subject_key], errors="ignore")
    neighbors = neighbors[neighbors > 0].sort_values(ascending=False)
    if neighbors.empty:
        return []

    scores: dict[int, float] = {}
    for neighbor_key, similarity_score in neighbors.items():
        neighbor_ratings = matrix.loc[neighbor_key]
        for book_id, value in neighbor_ratings.items():
            if value <= 0 or int(book_id) in seen_ids:
                continue
            scores[int(book_id)] = (
                scores.get(int(book_id), 0.0) + float(similarity_score) * float(value)
            )
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]


def _normalize_scores(recommendations: List[Tuple[int, float]]) -> dict[int, float]:
    if not recommendations:
        return {}
    values = [score for _, score in recommendations]
    max_score = max(values)
    min_score = min(values)
    if max_score == min_score:
        return {book_id: 1.0 for book_id, _ in recommendations}
    return {
        book_id: (score - min_score) / (max_score - min_score)
        for book_id, score in recommendations
    }


def _hybrid_recommendations(
    subject_key: str,
    matrix: pd.DataFrame | None,
    item_similarity: pd.DataFrame | None,
    user_similarity: pd.DataFrame | None,
    hot_books: List[Book],
    rated_book_ids: Iterable[int],
    top_k: int,
) -> List[Tuple[int, float]]:
    seen_ids = set(rated_book_ids)
    item_scores = _normalize_scores(
        _itemcf_recommendations_from_similarity(
            subject_key,
            matrix,
            item_similarity,
            top_k * 3,
        )
    )
    user_scores = _normalize_scores(
        _usercf_recommendations_from_similarity(
            subject_key,
            matrix,
            user_similarity,
            top_k * 3,
        )
    )
    hot_candidates = [
        (book.id, float(len(hot_books) - idx))
        for idx, book in enumerate(hot_books)
        if book.id not in seen_ids
    ]
    hot_scores = _normalize_scores(hot_candidates)
    candidate_ids = list(dict.fromkeys([*item_scores.keys(), *user_scores.keys(), *hot_scores.keys()]))
    combined = {
        book_id: item_scores.get(book_id, 0.0) * 0.5
        + user_scores.get(book_id, 0.0) * 0.3
        + hot_scores.get(book_id, 0.0) * 0.2
        for book_id in candidate_ids
    }
    return sorted(combined.items(), key=lambda item: item[1], reverse=True)[:top_k]


def itemcf_recommendations_for_user(user_id: int, top_k: int = 20) -> List[Tuple[int, float]]:
    frame = _build_interaction_frame()
    matrix = _build_interaction_matrix(frame)
    similarity = _compute_item_similarity(matrix)
    return _itemcf_recommendations_from_similarity(site_subject_key(user_id), matrix, similarity, top_k)


def _rebuild_similar_books(similarity: pd.DataFrame | None, top_k: int) -> int:
    if similarity is None or similarity.empty:
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


def _cache_result(cache_warnings: List[str], label: str, cache_writer, *args) -> None:
    try:
        cache_writer(*args)
    except Exception as exc:  # pragma: no cover - backend-specific in production
        cache_warnings.append(f"{label}_cache_failed={exc.__class__.__name__}: {exc}")


def rebuild_recommendations_for_all_users(top_k: int = 20) -> OfflineJobRun:
    now = timezone.now()
    job = OfflineJobRun.objects.create(job_name="rebuild_recommendations", status="running", started_at=now)
    processed_users = 0
    summary_parts: List[str] = []
    cache_warnings: List[str] = []

    try:
        frame = _build_interaction_frame()
        matrix = _build_interaction_matrix(frame)
        similarity = _compute_item_similarity(matrix)
        user_similarity = _compute_user_similarity(matrix)
        hot_books = hot_recommendations(top_k=top_k)
        user_cache_targets = []
        usercf_users = 0
        hybrid_users = 0

        with transaction.atomic():
            RecommendationResult.objects.filter(strategy__in=["hot", "itemcf", "usercf", "hybrid"]).delete()
            SimilarBookResult.objects.all().delete()

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
            summary_parts.append(f"hot_items={len(hot_items)}")

            similar_count = _rebuild_similar_books(similarity, top_k=min(top_k, 10))
            summary_parts.append(f"similar_pairs={similar_count}")

            for user in eligible_users():
                user_id = int(user.id)
                subject_key = site_subject_key(user_id)
                rated_book_ids = list(UserRating.objects.filter(user_id=user_id).values_list("book_id", flat=True))
                recommendations = _itemcf_recommendations_from_similarity(subject_key, matrix, similarity, top_k)
                reason = "Similar to your ratings"
                if not recommendations:
                    fallback_books = _hot_fallback_books_for_user(rated_book_ids, top_k=top_k)
                    recommendations = [
                        (book.id, float(book.rating_count) + float(book.average_rating))
                        for book in fallback_books
                    ]
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
                user_cache_targets.append((user_id, result))
                processed_users += 1

                usercf_recommendations = _usercf_recommendations_from_similarity(
                    subject_key,
                    matrix,
                    user_similarity,
                    top_k,
                )
                if usercf_recommendations:
                    usercf_result = RecommendationResult.objects.create(
                        user_id=user_id,
                        strategy="usercf",
                        generated_at=timezone.now(),
                        top_k=top_k,
                    )
                    RecommendationItem.objects.bulk_create(
                        [
                            RecommendationItem(
                                result=usercf_result,
                                book_id=book_id,
                                rank=rank,
                                score=score,
                                reason="Similar readers also liked this",
                            )
                            for rank, (book_id, score) in enumerate(usercf_recommendations, start=1)
                        ]
                    )
                    usercf_users += 1

                hybrid_recommendations = _hybrid_recommendations(
                    subject_key,
                    matrix,
                    similarity,
                    user_similarity,
                    hot_books,
                    rated_book_ids,
                    top_k,
                )
                if hybrid_recommendations:
                    hybrid_result = RecommendationResult.objects.create(
                        user_id=user_id,
                        strategy="hybrid",
                        generated_at=timezone.now(),
                        top_k=top_k,
                    )
                    RecommendationItem.objects.bulk_create(
                        [
                            RecommendationItem(
                                result=hybrid_result,
                                book_id=book_id,
                                rank=rank,
                                score=score,
                                reason="Blended ItemCF, UserCF, and popularity signal",
                            )
                            for rank, (book_id, score) in enumerate(hybrid_recommendations, start=1)
                        ]
                    )
                    hybrid_users += 1

        _cache_result(cache_warnings, "hot", cache_hot_recommendations, hot_result)
        for user_id, result in user_cache_targets:
            _cache_result(cache_warnings, f"user:{user_id}", cache_user_recommendations, user_id, result)

        job.status = "success"
        summary_parts.append(f"itemcf_users={processed_users}")
        summary_parts.append(f"usercf_users={usercf_users}")
        summary_parts.append(f"hybrid_users={hybrid_users}")
        if cache_warnings:
            summary_parts.append(f"cache_warnings={len(cache_warnings)}")
            summary_parts.extend(cache_warnings)
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
