import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating, UserRatingHistory


@pytest.mark.django_db
def test_user_rating_is_unique_for_user_and_book():
    user = get_user_model().objects.create_user(username="demo", email="demo@example.com", password="pass12345")
    category = Category.objects.create(name="Fiction", slug="fiction")
    book = Book.objects.create(
        title="Demo Book",
        author="Demo Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2020,
    )
    UserRating.objects.create(user=user, book=book, score=4)
    with pytest.raises(Exception):
        UserRating.objects.create(user=user, book=book, score=5)


@pytest.mark.django_db
def test_rating_history_records_action_type():
    user = get_user_model().objects.create_user(username="demo2", email="demo2@example.com", password="pass12345")
    category = Category.objects.create(name="History", slug="history")
    book = Book.objects.create(
        title="History Book",
        author="Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2021,
    )
    history = UserRatingHistory.objects.create(user=user, book=book, score=3, action="create")
    assert history.action == "create"
