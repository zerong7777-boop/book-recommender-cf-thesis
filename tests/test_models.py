import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating, UserRatingHistory
from apps.recommendations.models import RecommendationItem, RecommendationResult, SimilarBookResult


def create_book(*, name: str, slug: str) -> Book:
    category = Category.objects.create(name=name, slug=slug)
    return Book.objects.create(
        title=f"{name} Book",
        author="Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2024,
    )


@pytest.mark.django_db
def test_user_rating_is_unique_for_user_and_book():
    user = get_user_model().objects.create_user(username="demo", email="demo@example.com", password="pass12345")
    book = create_book(name="Fiction", slug="fiction")
    UserRating.objects.create(user=user, book=book, score=4)
    with pytest.raises(IntegrityError):
        UserRating.objects.create(user=user, book=book, score=5)


@pytest.mark.django_db
def test_rating_history_records_action_type():
    user = get_user_model().objects.create_user(username="demo2", email="demo2@example.com", password="pass12345")
    book = create_book(name="History", slug="history")
    history = UserRatingHistory.objects.create(user=user, book=book, score=3, action="create")
    assert history.action == "create"


@pytest.mark.django_db(transaction=True)
def test_rating_scores_must_stay_within_one_to_five():
    user = get_user_model().objects.create_user(username="demo3", email="demo3@example.com", password="pass12345")
    book = create_book(name="Science", slug="science")

    rating = UserRating(user=user, book=book, score=6)
    with pytest.raises(ValidationError):
        rating.full_clean()
    with pytest.raises(IntegrityError):
        UserRating.objects.create(user=user, book=book, score=6)

    history = UserRatingHistory(user=user, book=book, score=0, action="create")
    with pytest.raises(ValidationError):
        history.full_clean()
    with pytest.raises(IntegrityError):
        UserRatingHistory.objects.create(user=user, book=book, score=0, action="create")


@pytest.mark.django_db
def test_book_average_rating_must_match_rating_scale():
    book = create_book(name="Math", slug="math")

    book.average_rating = 5.5
    with pytest.raises(ValidationError):
        book.full_clean()

    with pytest.raises(IntegrityError):
        Book.objects.create(
            title="Invalid Average",
            author="Author",
            category=book.category,
            description="desc",
            publisher="pub",
            publication_year=2024,
            average_rating=-0.1,
        )


@pytest.mark.django_db(transaction=True)
def test_recommendation_item_unique_constraints_prevent_duplicate_rank_and_book():
    user = get_user_model().objects.create_user(username="demo4", email="demo4@example.com", password="pass12345")
    first_book = create_book(name="Poetry", slug="poetry")
    second_book = create_book(name="Travel", slug="travel")
    result = RecommendationResult.objects.create(user=user, strategy="hybrid", generated_at="2026-01-01T00:00:00Z")

    RecommendationItem.objects.create(result=result, book=first_book, rank=1, score=0.9)
    with pytest.raises(IntegrityError):
        RecommendationItem.objects.create(result=result, book=second_book, rank=1, score=0.8)
    with pytest.raises(IntegrityError):
        RecommendationItem.objects.create(result=result, book=first_book, rank=2, score=0.7)


@pytest.mark.django_db(transaction=True)
def test_similar_book_result_unique_constraints_prevent_duplicate_rank_and_target():
    source_book = create_book(name="Biography", slug="biography")
    first_target = create_book(name="Memoir", slug="memoir")
    second_target = create_book(name="Essay", slug="essay")

    SimilarBookResult.objects.create(source_book=source_book, target_book=first_target, score=0.9, rank=1)
    with pytest.raises(IntegrityError):
        SimilarBookResult.objects.create(source_book=source_book, target_book=second_target, score=0.8, rank=1)
    with pytest.raises(IntegrityError):
        SimilarBookResult.objects.create(source_book=source_book, target_book=first_target, score=0.7, rank=2)
