import pandas as pd
from django.db import transaction

from apps.ratings.models import ImportedInteraction, UserRating, UserRatingHistory


def site_subject_key(user_id: int) -> str:
    return f"site:{int(user_id)}"


def imported_subject_key(dataset_name: str, dataset_user_id: int) -> str:
    return f"{dataset_name}:{int(dataset_user_id)}"


def build_interaction_frame(include_event_metadata: bool = False) -> pd.DataFrame:
    rows = [
        {
            "subject_key": site_subject_key(row["user_id"]),
            "subject_label": site_subject_key(row["user_id"]),
            "book_id": int(row["book_id"]),
            "score": int(row["score"]),
            "event_id": int(row["id"]),
            "event_at": row["rated_at"],
            "source": "site",
        }
        for row in UserRating.objects.values("id", "user_id", "book_id", "score", "rated_at")
    ]
    rows.extend(
        {
            "subject_key": imported_subject_key(row["dataset_name"], row["dataset_user_id"]),
            "subject_label": imported_subject_key(row["dataset_name"], row["dataset_user_id"]),
            "book_id": int(row["book_id"]),
            "score": int(row["score"]),
            "event_id": int(row["id"]),
            "event_at": row["imported_at"],
            "source": row["dataset_name"],
        }
        for row in ImportedInteraction.objects.values(
            "id",
            "dataset_name",
            "dataset_user_id",
            "book_id",
            "score",
            "imported_at",
        )
    )
    columns = ["subject_key", "subject_label", "book_id", "score", "event_id", "event_at", "source"]
    if not rows:
        return pd.DataFrame(columns=columns if include_event_metadata else ["subject_key", "book_id", "score"])
    frame = pd.DataFrame.from_records(rows, columns=columns)
    frame = frame.sort_values(["subject_key", "event_at", "event_id"]).reset_index(drop=True)
    if include_event_metadata:
        return frame
    return frame[["subject_key", "book_id", "score"]].copy()


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
