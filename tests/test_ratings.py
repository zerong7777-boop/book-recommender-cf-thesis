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
    assert UserRating.objects.get(user=user, book=book).score == 5
    assert UserRatingHistory.objects.filter(user=user, book=book, action="create").exists()
