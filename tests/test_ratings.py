import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Book, Category
from apps.ratings.models import ImportedInteraction, UserRating, UserRatingHistory
from apps.recommendations.cache import user_recommendation_cache_key
from apps.recommendations.models import RecommendationItem, RecommendationResult


@pytest.mark.django_db
def test_rating_write_updates_database(client):
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Sci-Fi", slug="sci-fi")
    book = Book.objects.create(
        title="Space",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
    )
    client.login(username="reader", password="ReaderPass123")
    response = client.post(reverse("ratings:rate-book", args=[book.pk]), {"score": 5})
    assert response.status_code == 302
    assert response.url == reverse("catalog:book_detail", args=[book.pk])
    assert UserRating.objects.get(user=user, book=book).score == 5
    assert UserRatingHistory.objects.filter(user=user, book=book, action="create").exists()


@pytest.mark.django_db
def test_rating_write_refreshes_current_user_recommendations_and_cache(client):
    cache.clear()
    user = get_user_model().objects.create_user(
        username="instant-reader",
        email="instant-reader@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Instant", slug="instant")
    books = [
        Book.objects.create(
            title=f"Anchor {idx}",
            author="Author",
            category=category,
            description="d",
            publisher="p",
            publication_year=2020,
            rating_count=10,
            average_rating=4.0,
        )
        for idx in range(1, 4)
    ]
    target = Book.objects.create(
        title="Fresh Recommendation",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2021,
        rating_count=2,
        average_rating=4.8,
    )
    for book in books[:2]:
        UserRating.objects.create(user=user, book=book, score=5)
    for dataset_user_id, anchor in enumerate(books, start=100):
        ImportedInteraction.objects.create(dataset_user_id=dataset_user_id, book=anchor, score=5)
        ImportedInteraction.objects.create(dataset_user_id=dataset_user_id, book=target, score=5)

    client.login(username="instant-reader", password="ReaderPass123")
    response = client.post(reverse("ratings:rate-book", args=[books[2].pk]), {"score": 5})

    assert response.status_code == 302
    result = RecommendationResult.objects.get(user=user, strategy="itemcf")
    item_ids = set(result.items.values_list("book_id", flat=True))
    assert target.id in item_ids
    assert books[2].id not in item_ids
    payload = cache.get(user_recommendation_cache_key(user.id))
    assert payload is not None
    assert payload["strategy"] == "itemcf"
    assert target.id in {item["book_id"] for item in payload["items"]}


@pytest.mark.django_db
def test_rating_update_creates_history_update_action(client):
    user = get_user_model().objects.create_user(
        username="updater",
        email="updater@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Fantasy", slug="fantasy")
    book = Book.objects.create(
        title="Dragon",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2021,
    )

    client.login(username="updater", password="ReaderPass123")
    client.post(reverse("ratings:rate-book", args=[book.pk]), {"score": 4})
    response = client.post(reverse("ratings:rate-book", args=[book.pk]), {"score": 2})

    assert response.status_code == 302
    assert UserRating.objects.get(user=user, book=book).score == 2
    assert UserRatingHistory.objects.filter(user=user, book=book, action="create").exists()
    update_history = UserRatingHistory.objects.get(user=user, book=book, action="update")
    assert update_history.score == 2


@pytest.mark.django_db
def test_delete_rating_creates_history_delete_action(client):
    user = get_user_model().objects.create_user(
        username="deleter",
        email="deleter@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Thriller", slug="thriller")
    book = Book.objects.create(
        title="Gone",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2019,
    )
    UserRating.objects.create(user=user, book=book, score=3)

    client.login(username="deleter", password="ReaderPass123")
    response = client.post(reverse("ratings:delete-rating", args=[book.pk]))

    assert response.status_code == 302
    assert response.url == reverse("accounts:profile")
    assert not UserRating.objects.filter(user=user, book=book).exists()
    delete_history = UserRatingHistory.objects.get(user=user, book=book, action="delete")
    assert delete_history.score == 3


@pytest.mark.django_db
def test_delete_rating_clears_personalized_recommendations_when_user_returns_to_cold_start(client):
    cache.clear()
    user = get_user_model().objects.create_user(
        username="cold-again",
        email="cold-again@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Cold Again", slug="cold-again")
    books = [
        Book.objects.create(
            title=f"Rated {idx}",
            author="Author",
            category=category,
            description="d",
            publisher="p",
            publication_year=2020,
        )
        for idx in range(1, 4)
    ]
    for book in books:
        UserRating.objects.create(user=user, book=book, score=4)
    result = RecommendationResult.objects.create(user=user, strategy="itemcf", generated_at=timezone.now(), top_k=20)
    RecommendationItem.objects.create(result=result, book=books[0], rank=1, score=1.0, reason="stale")
    cache.set(user_recommendation_cache_key(user.id), {"strategy": "itemcf", "items": []}, timeout=None)

    client.login(username="cold-again", password="ReaderPass123")
    response = client.post(reverse("ratings:delete-rating", args=[books[0].pk]))

    assert response.status_code == 302
    assert not RecommendationResult.objects.filter(user=user, strategy="itemcf").exists()
    assert cache.get(user_recommendation_cache_key(user.id)) is None


@pytest.mark.django_db
def test_rating_rejects_out_of_range_score(client):
    user = get_user_model().objects.create_user(
        username="invalid-score",
        email="invalid-score@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Mystery", slug="mystery")
    book = Book.objects.create(
        title="Missing",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2018,
    )

    client.login(username="invalid-score", password="ReaderPass123")
    response = client.post(reverse("ratings:rate-book", args=[book.pk]), {"score": 6})

    assert response.status_code == 200
    assert "score" in response.context["form"].errors
    assert not UserRating.objects.filter(user=user, book=book).exists()
    assert not UserRatingHistory.objects.filter(user=user, book=book).exists()


@pytest.mark.django_db
def test_first_rate_page_lists_popular_books_for_new_user(client):
    get_user_model().objects.create_user(
        username="new-reader",
        email="new-reader@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Fiction", slug="fiction")
    Book.objects.create(
        title="Popular Novel",
        author="Author",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
        rating_count=12,
        average_rating=4.8,
    )

    client.login(username="new-reader", password="ReaderPass123")
    response = client.get(reverse("ratings:first-rate"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Popular Novel" in content
    assert "快速评分" in content
    assert "适合先评分的热门图书" in content


@pytest.mark.django_db
def test_rate_book_page_shows_score_guidance(client):
    get_user_model().objects.create_user(
        username="guide-reader",
        email="guide-reader@example.com",
        password="ReaderPass123",
    )
    category = Category.objects.create(name="Drama", slug="drama")
    book = Book.objects.create(
        title="Stage Light",
        author="Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2022,
    )

    client.login(username="guide-reader", password="ReaderPass123")
    response = client.get(reverse("ratings:rate-book", args=[book.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "请选择 1 到 5 之间的评分" in content
    assert "Stage Light" in content
