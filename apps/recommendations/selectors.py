from django.core.cache import cache

from apps.recommendations.cache import hot_recommendation_cache_key, user_recommendation_cache_key
from apps.recommendations.models import RecommendationResult, SimilarBookResult


def recommendation_state_for_user(user):
    if not user.is_authenticated:
        return "hot"
    if user.ratings.count() < 3:
        return "cold-start"
    return "personalized"


def _serialize_result(result):
    return {
        "generated_at": result.generated_at.isoformat(),
        "strategy": result.strategy,
        "items": [
            {
                "book_id": item.book_id,
                "title": item.book.title,
                "author": item.book.author,
                "category": item.book.category.name,
                "category_slug": item.book.category.slug,
                "cover_url": item.book.cover_url,
                "average_rating": float(item.book.average_rating),
                "reason": item.reason,
                "rank": item.rank,
            }
            for item in result.items.select_related("book", "book__category").order_by("rank")
        ],
    }


def _homepage_items(payload):
    if not payload:
        return []
    return [
        {
            "pk": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "cover_url": item.get("cover_url", ""),
            "category": {
                "name": item["category"],
                "slug": item.get("category_slug", ""),
            },
        }
        for item in payload.get("items", [])
    ]


def recommendation_block_for_user(user):
    state = recommendation_state_for_user(user)
    payload = None
    if state == "personalized":
        payload = cache.get(user_recommendation_cache_key(user.id))
        if payload is None:
            latest = RecommendationResult.objects.filter(user=user, strategy="itemcf").order_by("-generated_at").first()
            if latest is not None:
                payload = _serialize_result(latest)
    else:
        payload = cache.get(hot_recommendation_cache_key())
        if payload is None:
            latest = RecommendationResult.objects.filter(user__isnull=True, strategy="hot").order_by("-generated_at").first()
            if latest is not None:
                payload = _serialize_result(latest)
    return {
        "state": state,
        "payload": payload,
        "payload_items": payload.get("items", []) if payload else [],
        "items": _homepage_items(payload),
    }


def homepage_recommendation_block(user):
    return recommendation_block_for_user(user)


def similar_books_for_detail(book, user):
    return SimilarBookResult.objects.select_related("target_book", "target_book__category").filter(source_book=book)[:6]
