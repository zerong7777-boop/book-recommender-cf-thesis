from django.db import transaction

from apps.ratings.models import UserRating, UserRatingHistory


@transaction.atomic
def upsert_rating(*, user, book, score: int):
    rating, created = UserRating.objects.update_or_create(
        user=user,
        book=book,
        defaults={"score": score},
    )
    UserRatingHistory.objects.create(
        user=user,
        book=book,
        score=score,
        action="create" if created else "update",
    )
    return rating


@transaction.atomic
def delete_rating(*, user, book):
    try:
        rating = UserRating.objects.get(user=user, book=book)
    except UserRating.DoesNotExist:
        return False

    UserRatingHistory.objects.create(
        user=rating.user,
        book=rating.book,
        score=rating.score,
        action="delete",
    )
    rating.delete()
    return True
