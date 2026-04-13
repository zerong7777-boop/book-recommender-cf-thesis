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
        imported_books = 0
        imported_ratings = 0

        with transaction.atomic():
            for row in books_frame.to_dict("records"):
                title = str(row.get("title", "")).strip()
                author = str(row.get("authors", "")).strip() or "Unknown Author"
                if not title:
                    continue
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
                    imported_books += 1

            for row in ratings_frame.to_dict("records"):
                score = _clean_score(row.get("rating"))
                book = book_map.get(int(row.get("book_id")))
                if book is None or score is None:
                    continue
                ImportedInteraction.objects.update_or_create(
                    dataset_name="goodbooks-10k",
                    dataset_user_id=int(row["user_id"]),
                    book=book,
                    defaults={"score": score},
                )
                imported_ratings += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported goodbooks data: books_created={imported_books}, interactions_processed={imported_ratings}"
            )
        )
