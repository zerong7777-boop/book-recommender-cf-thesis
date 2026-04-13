from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Book, Category
from apps.ratings.models import ImportedInteraction


DEFAULT_CATEGORY_NAME = "Goodbooks Import"
DEFAULT_CATEGORY_SLUG = "goodbooks-import"


def _clean_year(value):
    if pd.isna(value):
        return None
    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None
    return year if year > 0 else None


def _clean_score(value):
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 5 else None


class Command(BaseCommand):
    help = "Import Goodbooks-style books and ratings CSV files"

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Directory containing books.csv and ratings.csv")
        parser.add_argument(
            "--limit-ratings",
            type=int,
            default=None,
            help="Optional maximum number of ratings rows to import for local smoke runs.",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source"]).resolve()
        books_path = source_dir / "books.csv"
        ratings_path = source_dir / "ratings.csv"
        if not books_path.exists() or not ratings_path.exists():
            raise CommandError("books.csv and ratings.csv must both exist under --source")

        books_frame = pd.read_csv(books_path)
        ratings_frame = pd.read_csv(ratings_path)
        required_book_columns = {"book_id", "title", "authors"}
        required_rating_columns = {"user_id", "book_id", "rating"}
        if not required_book_columns.issubset(books_frame.columns):
            raise CommandError(f"books.csv must contain columns: {sorted(required_book_columns)}")
        if not required_rating_columns.issubset(ratings_frame.columns):
            raise CommandError(f"ratings.csv must contain columns: {sorted(required_rating_columns)}")

        category, _ = Category.objects.get_or_create(
            slug=DEFAULT_CATEGORY_SLUG,
            defaults={"name": DEFAULT_CATEGORY_NAME},
        )
        book_map: dict[int, Book] = {}
        books_processed = 0
        books_created = 0
        books_updated = 0
        interactions_created = 0
        interactions_updated = 0
        limit_ratings = options["limit_ratings"]

        with transaction.atomic():
            for row in books_frame.to_dict("records"):
                title = str(row.get("title", "")).strip()
                author = str(row.get("authors", "")).strip() or "Unknown Author"
                if not title:
                    continue
                books_processed += 1
                book, created = Book.objects.update_or_create(
                    title=title,
                    author=author,
                    category=category,
                    defaults={
                        "description": "Imported from Goodbooks baseline data.",
                        "publisher": "",
                        "publication_year": _clean_year(row.get("original_publication_year")),
                        "average_rating": float(row.get("average_rating", 0.0) or 0.0),
                        "rating_count": int(row.get("ratings_count", 0) or 0),
                        "cover_url": str(row.get("image_url", "") or ""),
                    },
                )
                book_map[int(row["book_id"])] = book
                if created:
                    books_created += 1
                else:
                    books_updated += 1

            rating_rows = ratings_frame.to_dict("records")
            if limit_ratings is not None:
                rating_rows = rating_rows[: max(limit_ratings, 0)]
            for row in rating_rows:
                score = _clean_score(row.get("rating"))
                book = book_map.get(int(row.get("book_id")))
                if book is None or score is None:
                    continue
                _, created = ImportedInteraction.objects.update_or_create(
                    dataset_name="goodbooks-10k",
                    dataset_user_id=int(row["user_id"]),
                    book=book,
                    defaults={"score": score},
                )
                if created:
                    interactions_created += 1
                else:
                    interactions_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported goodbooks data: "
                f"books_processed={books_processed}, "
                f"books_created={books_created}, "
                f"books_updated={books_updated}, "
                f"interactions_created={interactions_created}, "
                f"interactions_updated={interactions_updated}"
            )
        )
