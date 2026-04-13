from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command

from apps.catalog.models import Book, Category
from apps.ratings.models import ImportedInteraction


TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_testdata"


def make_temp_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{prefix}{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


@pytest.mark.django_db
def test_import_goodbooks_loads_books_categories_and_interactions():
    tmp_path = make_temp_dir("goodbooks-import-")
    source_dir = tmp_path / "goodbooks"
    source_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        source_dir / "books.csv",
        """
book_id,title,authors,original_publication_year,average_rating,ratings_count,image_url
1,Signals in the Stacks,A. Curator,2021,4.5,20,https://example.com/1.jpg
2,Quiet Algorithms,B. Reader,2020,4.2,15,https://example.com/2.jpg
        """,
    )
    _write_csv(
        source_dir / "ratings.csv",
        """
user_id,book_id,rating
10,1,5
10,2,4
11,1,3
        """,
    )

    call_command("import_goodbooks", source=str(source_dir))

    assert Book.objects.filter(title="Signals in the Stacks").exists()
    assert Book.objects.filter(title="Quiet Algorithms").exists()
    assert Category.objects.filter(slug="goodbooks-import").exists()
    assert ImportedInteraction.objects.count() == 3
    assert ImportedInteraction.objects.filter(dataset_user_id=10, book__title="Signals in the Stacks", score=5).exists()


@pytest.mark.django_db
def test_import_goodbooks_is_idempotent_for_books_and_interactions():
    tmp_path = make_temp_dir("goodbooks-idempotent-")
    source_dir = tmp_path / "goodbooks"
    source_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        source_dir / "books.csv",
        """
book_id,title,authors,original_publication_year,average_rating,ratings_count,image_url
1,Repeatable Import,A. Curator,2021,4.5,20,https://example.com/1.jpg
        """,
    )
    _write_csv(
        source_dir / "ratings.csv",
        """
user_id,book_id,rating
10,1,5
        """,
    )

    call_command("import_goodbooks", source=str(source_dir))
    call_command("import_goodbooks", source=str(source_dir))

    assert Book.objects.filter(title="Repeatable Import").count() == 1
    assert ImportedInteraction.objects.count() == 1


@pytest.mark.django_db
def test_import_goodbooks_reports_created_and_updated_counts(capsys):
    tmp_path = make_temp_dir("goodbooks-summary-")
    source_dir = tmp_path / "goodbooks"
    source_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        source_dir / "books.csv",
        """
book_id,title,authors,original_publication_year,average_rating,ratings_count,image_url
1,Counted Import,A. Curator,2021,4.5,20,https://example.com/1.jpg
        """,
    )
    _write_csv(
        source_dir / "ratings.csv",
        """
user_id,book_id,rating
10,1,5
        """,
    )

    call_command("import_goodbooks", source=str(source_dir))
    call_command("import_goodbooks", source=str(source_dir))

    output = capsys.readouterr().out
    assert "books_processed=1" in output
    assert "books_created=0" in output
    assert "books_updated=1" in output
    assert "interactions_created=0" in output
    assert "interactions_updated=1" in output


@pytest.mark.django_db
def test_import_goodbooks_can_limit_ratings_for_local_smoke_import():
    tmp_path = make_temp_dir("goodbooks-limit-")
    source_dir = tmp_path / "goodbooks"
    source_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        source_dir / "books.csv",
        """
book_id,title,authors,original_publication_year,average_rating,ratings_count,image_url
1,Limited Import A,A. Curator,2021,4.5,20,https://example.com/1.jpg
2,Limited Import B,B. Curator,2020,4.0,10,https://example.com/2.jpg
        """,
    )
    _write_csv(
        source_dir / "ratings.csv",
        """
user_id,book_id,rating
10,1,5
10,2,4
11,1,3
        """,
    )

    call_command("import_goodbooks", source=str(source_dir), limit_ratings=2)

    assert ImportedInteraction.objects.count() == 2
