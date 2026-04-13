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
    assert "Quick-start rating" in content
    assert "Popular books to rate first" in content


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
    assert "Choose a score from 1 to 5" in content
    assert "Stage Light" in content
