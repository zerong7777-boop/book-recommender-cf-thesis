import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating, UserRatingHistory


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
    assert "Popular Novel" in response.content.decode()
