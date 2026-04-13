from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "book_recommender.settings")

import django

django.setup()

from django.core.cache import cache

from apps.recommendations.cache import hot_recommendation_cache_key, user_recommendation_cache_key
from apps.recommendations.models import RecommendationResult
from apps.recommendations.services import rebuild_recommendations_for_all_users


def main() -> int:
    job = rebuild_recommendations_for_all_users(top_k=20)
    if job.status != "success":
        print(f"rebuild_failed status={job.status} summary={job.summary}")
        return 1

    hot_result = RecommendationResult.objects.filter(user__isnull=True, strategy="hot").latest("generated_at")
    hot_payload = cache.get(hot_recommendation_cache_key())
    if not hot_payload:
        print("redis_hot_cache_missing")
        return 1

    user_result = RecommendationResult.objects.filter(user__isnull=False, strategy="itemcf").order_by("-generated_at").first()
    if user_result and not cache.get(user_recommendation_cache_key(user_result.user_id)):
        print(f"redis_user_cache_missing user_id={user_result.user_id}")
        return 1

    print(f"redis_cache_path_ok hot_result_id={hot_result.id} processed_users={job.processed_user_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
