from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "book_recommender.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating
from apps.ratings.services import upsert_rating
from apps.recommendations.services import rebuild_recommendations_for_all_users


DEMO_ADMIN_USERNAME = "thesis_admin"
DEMO_ADMIN_PASSWORD = "AdminPass123!"
DEMO_USER_USERNAME = "demo_reader"
DEMO_USER_PASSWORD = "DemoPass123!"
EVAL_SHADOW_PASSWORD = "EvalShadow123!"


@dataclass(frozen=True)
class SampleBookSpec:
    title: str
    author: str
    category_name: str
    category_slug: str
    description: str
    publisher: str
    publication_year: int
    average_rating: float
    rating_count: int


SAMPLE_BOOKS: tuple[SampleBookSpec, ...] = (
    SampleBookSpec(
        title="Neural Networks for Readers",
        author="A. Researcher",
        category_name="Computer Science",
        category_slug="computer-science",
        description="A short thesis-friendly primer on recommendation systems and neural models.",
        publisher="Campus Press",
        publication_year=2022,
        average_rating=4.6,
        rating_count=28,
    ),
    SampleBookSpec(
        title="The Quiet Shelf",
        author="M. Editor",
        category_name="Literary Fiction",
        category_slug="literary-fiction",
        description="A reflective novel about memory, study habits, and finding a good reading list.",
        publisher="Thesis House",
        publication_year=2021,
        average_rating=4.4,
        rating_count=24,
    ),
    SampleBookSpec(
        title="Signals in the Library",
        author="J. Analyst",
        category_name="Data Science",
        category_slug="data-science",
        description="How collaborative filtering picks up patterns from a small, curated dataset.",
        publisher="Signal Press",
        publication_year=2023,
        average_rating=4.8,
        rating_count=32,
    ),
    SampleBookSpec(
        title="Reading the Past",
        author="L. Historian",
        category_name="History",
        category_slug="history",
        description="A compact guide to archival reading and the structure of evidence.",
        publisher="Archive Books",
        publication_year=2020,
        average_rating=4.1,
        rating_count=19,
    ),
    SampleBookSpec(
        title="Foundations of Recommendation",
        author="K. Scholar",
        category_name="Computer Science",
        category_slug="computer-science",
        description="Foundational concepts for a thesis demo on recommendation pipelines.",
        publisher="Campus Press",
        publication_year=2024,
        average_rating=4.7,
        rating_count=35,
    ),
)


def _ensure_admin_account():
    user_model = get_user_model()
    admin_defaults = {
        "email": "thesis_admin@example.com",
        "is_staff": True,
        "is_superuser": True,
    }
    admin, created = user_model.objects.get_or_create(username=DEMO_ADMIN_USERNAME, defaults=admin_defaults)
    updated_fields = []
    for field, value in admin_defaults.items():
        if getattr(admin, field) != value:
            setattr(admin, field, value)
            updated_fields.append(field)
    if not admin.check_password(DEMO_ADMIN_PASSWORD):
        admin.set_password(DEMO_ADMIN_PASSWORD)
        updated_fields.append("password")
    if updated_fields:
        admin.save()
    elif created:
        admin.set_password(DEMO_ADMIN_PASSWORD)
        admin.save(update_fields=["password"])
    return admin


def _ensure_demo_user():
    user_model = get_user_model()
    demo_defaults = {
        "email": "demo_reader@example.com",
        "is_staff": False,
        "is_superuser": False,
    }
    demo_user, created = user_model.objects.get_or_create(username=DEMO_USER_USERNAME, defaults=demo_defaults)
    updated_fields = []
    for field, value in demo_defaults.items():
        if getattr(demo_user, field) != value:
            setattr(demo_user, field, value)
            updated_fields.append(field)
    if not demo_user.check_password(DEMO_USER_PASSWORD):
        demo_user.set_password(DEMO_USER_PASSWORD)
        updated_fields.append("password")
    if updated_fields:
        demo_user.save()
    elif created:
        demo_user.set_password(DEMO_USER_PASSWORD)
        demo_user.save(update_fields=["password"])
    return demo_user


def _ensure_eval_shadow_user(*, username: str, email: str):
    user_model = get_user_model()
    defaults = {
        "email": email,
        "is_staff": False,
        "is_superuser": False,
    }
    user, created = user_model.objects.get_or_create(username=username, defaults=defaults)
    updated_fields = []
    for field, value in defaults.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            updated_fields.append(field)
    if not user.check_password(EVAL_SHADOW_PASSWORD):
        user.set_password(EVAL_SHADOW_PASSWORD)
        updated_fields.append("password")
    if updated_fields:
        user.save()
    elif created:
        user.set_password(EVAL_SHADOW_PASSWORD)
        user.save(update_fields=["password"])
    return user


def _ensure_category(*, name: str, slug: str) -> Category:
    category, _ = Category.objects.update_or_create(slug=slug, defaults={"name": name})
    return category


def _ensure_book(*, spec: SampleBookSpec, category: Category) -> Book:
    book, _ = Book.objects.update_or_create(
        title=spec.title,
        author=spec.author,
        category=category,
        defaults={
            "description": spec.description,
            "publisher": spec.publisher,
            "publication_year": spec.publication_year,
            "average_rating": spec.average_rating,
            "rating_count": spec.rating_count,
        },
    )
    return book


def _seed_sample_catalog() -> list[Book]:
    books: list[Book] = []
    categories: dict[str, Category] = {}
    for spec in SAMPLE_BOOKS:
        category = categories.get(spec.category_slug)
        if category is None:
            category = _ensure_category(name=spec.category_name, slug=spec.category_slug)
            categories[spec.category_slug] = category
        books.append(_ensure_book(spec=spec, category=category))
    return books


def _seed_demo_ratings(demo_user, books: Iterable[Book]) -> tuple[int, int]:
    existing_book_ids = set(
        UserRating.objects.filter(user=demo_user, book__in=list(books)).values_list("book_id", flat=True)
    )
    created_count = 0
    updated_count = 0
    for score, book in zip((5, 4, 5), books):
        upsert_rating(user=demo_user, book=book, score=score)
        if book.id in existing_book_ids:
            updated_count += 1
        else:
            created_count += 1
    return created_count, updated_count


def _seed_eval_shadow_ratings(books: list[Book]) -> None:
    if len(books) < 5:
        return
    shadow_specs = (
        ("eval_reader_1", "eval_reader_1@example.com", ((books[0], 5), (books[1], 4), (books[3], 5))),
        ("eval_reader_2", "eval_reader_2@example.com", ((books[0], 4), (books[1], 5), (books[4], 5))),
        ("eval_reader_3", "eval_reader_3@example.com", ((books[0], 5), (books[2], 4), (books[3], 4))),
    )
    for username, email, ratings in shadow_specs:
        shadow_user = _ensure_eval_shadow_user(username=username, email=email)
        for book, score in ratings:
            upsert_rating(user=shadow_user, book=book, score=score)


@transaction.atomic
def _seed_demo_data(*, include_sample_catalog: bool = True):
    admin = _ensure_admin_account()
    demo_user = _ensure_demo_user()
    books = _seed_sample_catalog() if include_sample_catalog else list(Book.objects.order_by("id")[:3])
    if len(books) < 3:
        raise RuntimeError("At least 3 books are required to seed the demo account.")
    ratings_created, ratings_updated = _seed_demo_ratings(demo_user, books)
    _seed_eval_shadow_ratings(books)
    return {
        "admin": admin,
        "demo_user": demo_user,
        "books": books,
        "ratings_created": ratings_created,
        "ratings_updated": ratings_updated,
    }


def initialize_demo_data(*, include_sample_catalog: bool = True, rebuild_recommendations: bool = True):
    result = _seed_demo_data(include_sample_catalog=include_sample_catalog)
    job = None
    if rebuild_recommendations:
        job = rebuild_recommendations_for_all_users(top_k=10)
    result["rebuild_job"] = job
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize thesis demo data.")
    parser.add_argument("--no-sample-catalog", action="store_true", help="Skip creating the compact sample catalog.")
    parser.add_argument("--no-rebuild", action="store_true", help="Skip rebuilding recommendations after seeding.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = initialize_demo_data(
        include_sample_catalog=not args.no_sample_catalog,
        rebuild_recommendations=not args.no_rebuild,
    )
    print(
        "Demo data initialized: "
        f"admin={result['admin'].username}, "
        f"demo_user={result['demo_user'].username}, "
        f"ratings_created={result['ratings_created']}, "
        f"ratings_updated={result['ratings_updated']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
