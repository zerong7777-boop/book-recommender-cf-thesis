import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command

from apps.catalog.models import Book, Category
from apps.ratings.models import ImportedInteraction, UserRating
from apps.recommendations.cache import hot_recommendation_cache_key, user_recommendation_cache_key
from apps.recommendations.models import OfflineJobRun, RecommendationResult, SimilarBookResult
from apps.recommendations.services import rebuild_recommendations_for_all_users


def create_book(*, category: Category, title: str, rating_count: int, average_rating: float) -> Book:
    return Book.objects.create(
        title=title,
        author="Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2024,
        rating_count=rating_count,
        average_rating=average_rating,
    )


@pytest.mark.django_db
def test_rebuild_populates_hot_result_and_cache():
    cache.clear()
    category = Category.objects.create(name="Fiction", slug="fiction")
    create_book(category=category, title="Book A", rating_count=25, average_rating=4.2)
    create_book(category=category, title="Book B", rating_count=40, average_rating=3.9)
    create_book(category=category, title="Book C", rating_count=40, average_rating=4.8)

    rebuild_recommendations_for_all_users(top_k=2)

    hot_result = RecommendationResult.objects.get(user__isnull=True, strategy="hot")
    hot_items = list(hot_result.items.select_related("book").order_by("rank"))
    assert len(hot_items) == 2
    expected_books = list(Book.objects.order_by("-rating_count", "-average_rating")[:2])
    assert [item.book_id for item in hot_items] == [book.id for book in expected_books]

    payload = cache.get(hot_recommendation_cache_key())
    assert payload is not None
    assert payload["strategy"] == "hot"
    assert len(payload["items"]) == len(hot_items)
    assert {"book_id", "title", "author", "category", "average_rating", "reason", "rank"} <= set(payload["items"][0])
    assert {item["book"]["id"] for item in payload["items"]} == {item.book_id for item in hot_items}


@pytest.mark.django_db
def test_itemcf_fallback_excludes_rated_books_and_caches_payload():
    cache.clear()
    category = Category.objects.create(name="History", slug="history")
    rated_books = [
        create_book(category=category, title="Book 1", rating_count=12, average_rating=4.0),
        create_book(category=category, title="Book 2", rating_count=10, average_rating=4.4),
        create_book(category=category, title="Book 3", rating_count=8, average_rating=3.8),
    ]
    unrated_book = create_book(category=category, title="Book 4", rating_count=20, average_rating=4.9)

    user = get_user_model().objects.create_user(username="demo", email="demo@example.com", password="pass12345")
    for book in rated_books:
        UserRating.objects.create(user=user, book=book, score=4)

    rebuild_recommendations_for_all_users(top_k=3)

    result = RecommendationResult.objects.get(user=user, strategy="itemcf")
    items = list(result.items.select_related("book").order_by("rank"))
    assert items
    rated_ids = {book.id for book in rated_books}
    assert all(item.book_id not in rated_ids for item in items)
    assert all(
        item.reason == "Popular fallback because ItemCF had sparse data" for item in items
    )
    assert unrated_book.id in {item.book_id for item in items}

    payload = cache.get(user_recommendation_cache_key(user.id))
    assert payload is not None
    assert payload["strategy"] == "itemcf"
    cached_book_ids = [item["book"]["id"] for item in payload["items"]]
    assert set(cached_book_ids) == {item.book_id for item in items}


@pytest.mark.django_db
def test_cold_start_user_has_no_personalized_result_or_cache():
    cache.clear()
    category = Category.objects.create(name="SciFi", slug="scifi")
    books = [
        create_book(category=category, title="Book X", rating_count=5, average_rating=3.5),
        create_book(category=category, title="Book Y", rating_count=7, average_rating=4.1),
    ]
    user = get_user_model().objects.create_user(username="cold", email="cold@example.com", password="pass12345")
    for book in books:
        UserRating.objects.create(user=user, book=book, score=5)

    rebuild_recommendations_for_all_users(top_k=5)

    assert not RecommendationResult.objects.filter(user=user, strategy="itemcf").exists()
    assert cache.get(user_recommendation_cache_key(user.id)) is None


@pytest.mark.django_db
def test_management_command_records_success_job():
    cache.clear()
    category = Category.objects.create(name="Romance", slug="romance")
    create_book(category=category, title="Book R", rating_count=3, average_rating=4.0)

    call_command("rebuild_recommendations")

    job = OfflineJobRun.objects.latest("id")
    assert job.status == "success"
    assert job.job_name == "rebuild_recommendations"
    assert job.summary


@pytest.mark.django_db
def test_rebuild_replaces_prior_results_instead_of_duplicating():
    cache.clear()
    category = Category.objects.create(name="Classics", slug="classics")
    rated_books = [
        create_book(category=category, title="Rated 1", rating_count=12, average_rating=4.1),
        create_book(category=category, title="Rated 2", rating_count=11, average_rating=4.0),
        create_book(category=category, title="Rated 3", rating_count=10, average_rating=3.9),
    ]
    create_book(category=category, title="Candidate", rating_count=30, average_rating=4.9)
    user = get_user_model().objects.create_user(username="repeat", email="repeat@example.com", password="pass12345")
    for book in rated_books:
        UserRating.objects.create(user=user, book=book, score=4)

    rebuild_recommendations_for_all_users(top_k=3)
    rebuild_recommendations_for_all_users(top_k=3)

    assert RecommendationResult.objects.filter(user__isnull=True, strategy="hot").count() == 1
    assert RecommendationResult.objects.filter(user=user, strategy="itemcf").count() == 1


@pytest.mark.django_db
def test_rebuild_clears_stale_similar_books_when_no_similarity_can_be_computed():
    cache.clear()
    category = Category.objects.create(name="Poetry", slug="poetry")
    source = create_book(category=category, title="Source", rating_count=1, average_rating=3.0)
    target = create_book(category=category, title="Target", rating_count=1, average_rating=3.0)
    SimilarBookResult.objects.create(source_book=source, target_book=target, score=0.8, rank=1)

    rebuild_recommendations_for_all_users(top_k=3)

    assert not SimilarBookResult.objects.exists()


@pytest.mark.django_db
def test_rebuild_succeeds_with_cache_warning_when_cache_backend_fails(monkeypatch):
    cache.clear()
    category = Category.objects.create(name="Essays", slug="essays")
    create_book(category=category, title="Cached Later", rating_count=8, average_rating=4.3)

    def fail_cache_set(*args, **kwargs):
        raise ConnectionError("cache offline")

    monkeypatch.setattr("apps.recommendations.cache.cache.set", fail_cache_set)

    job = rebuild_recommendations_for_all_users(top_k=1)

    assert job.status == "success"
    assert "cache_warnings" in job.summary
    assert RecommendationResult.objects.filter(user__isnull=True, strategy="hot").exists()


@pytest.mark.django_db
def test_rebuild_uses_imported_interactions_to_strengthen_itemcf():
    cache.clear()
    category = Category.objects.create(name="Imported", slug="imported")
    books = [
        create_book(category=category, title="Anchor A", rating_count=5, average_rating=4.0),
        create_book(category=category, title="Anchor B", rating_count=5, average_rating=4.1),
        create_book(category=category, title="Anchor C", rating_count=5, average_rating=4.2),
        create_book(category=category, title="Imported Candidate", rating_count=2, average_rating=4.9),
    ]
    user = get_user_model().objects.create_user(
        username="withimport",
        email="withimport@example.com",
        password="pass12345",
    )
    for score, book in zip([5, 4, 4], books[:3], strict=True):
        UserRating.objects.create(user=user, book=book, score=score)

    ImportedInteraction.objects.create(dataset_user_id=100, book=books[0], score=5)
    ImportedInteraction.objects.create(dataset_user_id=100, book=books[3], score=5)
    ImportedInteraction.objects.create(dataset_user_id=101, book=books[1], score=5)
    ImportedInteraction.objects.create(dataset_user_id=101, book=books[3], score=4)
    ImportedInteraction.objects.create(dataset_user_id=102, book=books[2], score=5)
    ImportedInteraction.objects.create(dataset_user_id=102, book=books[3], score=4)

    rebuild_recommendations_for_all_users(top_k=3)

    result = RecommendationResult.objects.get(user=user, strategy="itemcf")
    items = list(result.items.select_related("book").order_by("rank"))
    assert items
    assert items[0].book_id == books[3].id
    assert items[0].reason == "Similar to your ratings"
