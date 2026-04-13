import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating
from apps.recommendations.cache import user_recommendation_cache_key
from apps.recommendations.models import RecommendationResult, SimilarBookResult


def create_book(*, category: Category, title: str) -> Book:
    return Book.objects.create(
        title=title,
        author="Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2024,
        average_rating=4.2,
        rating_count=12,
    )


@pytest.mark.django_db
def test_recommendation_page_requires_login(client):
    response = client.get(reverse("recommendations:list"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_recommendation_page_shows_cached_reason_for_authenticated_user(client):
    cache.clear()
    user = get_user_model().objects.create_user(username="reader", email="reader@example.com", password="ReaderPass123")
    category = Category.objects.create(name="Fiction", slug="fiction")
    rated_books = [create_book(category=category, title=f"Rated {idx}") for idx in range(1, 4)]
    recommended = create_book(category=category, title="Recommended Book")
    for book in rated_books:
        UserRating.objects.create(user=user, book=book, score=5)

    cache.set(
        user_recommendation_cache_key(user.id),
        {
            "generated_at": timezone.now().isoformat(),
            "strategy": "itemcf",
            "items": [
                {
                    "book_id": recommended.id,
                    "title": recommended.title,
                    "author": recommended.author,
                    "category": category.name,
                    "category_slug": category.slug,
                    "cover_url": recommended.cover_url,
                    "average_rating": float(recommended.average_rating),
                    "reason": "Because you liked Rated 1",
                    "rank": 1,
                }
            ],
        },
        timeout=None,
    )

    client.login(username="reader", password="ReaderPass123")
    response = client.get(reverse("recommendations:list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "personalized" in content
    assert "Recommended Book" in content
    assert "Because you liked Rated 1" in content


@pytest.mark.django_db
def test_book_detail_page_renders_similar_books_block(client):
    category = Category.objects.create(name="History", slug="history")
    source = create_book(category=category, title="Source Book")
    similar = create_book(category=category, title="Similar Book")
    RecommendationResult.objects.create(strategy="hot", generated_at=timezone.now(), top_k=20)
    SimilarBookResult.objects.create(source_book=source, target_book=similar, score=0.91, rank=1)

    response = client.get(reverse("catalog:book_detail", kwargs={"pk": source.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Similar Book" in content
    assert "0.91" in content


@pytest.mark.django_db
def test_book_detail_page_shows_personalized_recommendation_reason_for_logged_in_user(client):
    cache.clear()
    user = get_user_model().objects.create_user(username="detail-reader", email="detail@example.com", password="ReaderPass123")
    category = Category.objects.create(name="History", slug="history")
    rated_books = [create_book(category=category, title=f"Rated {idx}") for idx in range(1, 4)]
    target = create_book(category=category, title="Recommended Detail Book")
    for book in rated_books:
        UserRating.objects.create(user=user, book=book, score=5)
    cache.set(
        user_recommendation_cache_key(user.id),
        {
            "generated_at": timezone.now().isoformat(),
            "strategy": "itemcf",
            "items": [
                {
                    "book_id": target.id,
                    "title": target.title,
                    "author": target.author,
                    "category": category.name,
                    "category_slug": category.slug,
                    "cover_url": target.cover_url,
                    "average_rating": float(target.average_rating),
                    "reason": "Because you liked Rated 1",
                    "rank": 1,
                }
            ],
        },
        timeout=None,
    )

    client.login(username="detail-reader", password="ReaderPass123")
    response = client.get(reverse("catalog:book_detail", kwargs={"pk": target.pk}))

    content = response.content.decode()
    assert "Why this book is recommended to you" in content
    assert "Because you liked Rated 1" in content
    assert "Rank #1" in content
