from __future__ import annotations

from typing import Any, Dict, List

from django.core.cache import cache

from apps.recommendations.models import RecommendationResult

DEFAULT_CACHE_TIMEOUT = None


def user_recommendation_cache_key(user_id: int) -> str:
    return f"user:{user_id}:recs"


def hot_recommendation_cache_key() -> str:
    return "hot:recs"


def cache_user_recommendations(user_id: int, result: RecommendationResult) -> Dict[str, Any]:
    payload = _serialize_recommendation_result(result)
    cache.set(user_recommendation_cache_key(user_id), payload, timeout=DEFAULT_CACHE_TIMEOUT)
    return payload


def cache_hot_recommendations(result: RecommendationResult) -> Dict[str, Any]:
    payload = _serialize_recommendation_result(result)
    cache.set(hot_recommendation_cache_key(), payload, timeout=DEFAULT_CACHE_TIMEOUT)
    return payload


def _serialize_recommendation_result(result: RecommendationResult) -> Dict[str, Any]:
    items = result.items.select_related("book", "book__category").order_by("rank")
    serialized_items: List[Dict[str, Any]] = []
    for item in items:
        book = item.book
        category = book.category
        serialized_items.append(
            {
                "rank": item.rank,
                "score": float(item.score),
                "reason": item.reason,
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "category": category.name,
                "category_slug": category.slug,
                "cover_url": book.cover_url,
                "average_rating": float(book.average_rating),
                "book": {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "cover_url": book.cover_url,
                    "description": book.description,
                    "publisher": book.publisher,
                    "publication_year": book.publication_year,
                    "average_rating": float(book.average_rating),
                    "rating_count": book.rating_count,
                    "category": {
                        "id": category.id,
                        "name": category.name,
                        "slug": category.slug,
                    },
                },
            }
        )
    return {
        "strategy": result.strategy,
        "user_id": result.user_id,
        "generated_at": result.generated_at.isoformat(),
        "top_k": result.top_k,
        "items": serialized_items,
    }
