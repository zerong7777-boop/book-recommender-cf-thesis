import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.catalog.models import Book, Category
from apps.evaluations.services import evaluation_artifact_dir, k_values
from apps.ratings.models import UserRating


def test_k_values_match_spec():
    assert k_values() == [5, 10, 20, 30]


@pytest.mark.django_db
def test_evaluate_recommenders_writes_summary(settings, tmp_path):
    settings.BASE_DIR = tmp_path

    call_command("evaluate_recommenders")

    summary_path = evaluation_artifact_dir(tmp_path) / "summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert [entry["k"] for entry in payload["overview"]] == [5, 10, 20, 30]
    assert {entry["name"] for entry in payload["algorithms"]} == {"hot", "itemcf", "usercf", "hybrid"}


@pytest.mark.django_db
def test_evaluate_recommenders_computes_non_placeholder_metrics(settings, tmp_path, django_user_model):
    settings.BASE_DIR = tmp_path
    category = Category.objects.create(name="Eval", slug="eval")
    books = [
        Book.objects.create(
            title=f"Book {idx}",
            author="Author",
            category=category,
            description="desc",
            publisher="pub",
            publication_year=2024,
            average_rating=4.0 + (idx * 0.1),
            rating_count=10 + idx,
        )
        for idx in range(1, 6)
    ]
    user_specs = [
        ("u1", [books[0], books[1], books[2]]),
        ("u2", [books[0], books[1], books[3]]),
        ("u3", [books[0], books[1], books[4]]),
        ("u4", [books[0], books[2], books[3]]),
    ]
    for username, rated_books in user_specs:
        user = django_user_model.objects.create_user(username=username, password="ReaderPass123")
        for score, book in enumerate(rated_books, start=3):
            UserRating.objects.create(user=user, book=book, score=min(score, 5))

    call_command("evaluate_recommenders")

    payload = json.loads((evaluation_artifact_dir(tmp_path) / "summary.json").read_text(encoding="utf-8"))
    algorithm_payload = {entry["name"]: entry for entry in payload["algorithms"]}

    assert any(row["precision"] > 0 for row in payload["overview"])
    assert algorithm_payload["hot"]["user_count"] > 0
    assert algorithm_payload["itemcf"]["best_precision"] >= 0
    assert len(algorithm_payload["itemcf"]["metrics"]) == 4


def test_experiment_results_page_reads_summary(client, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(
        json.dumps(
            {
                "overview": [{"k": 5, "precision": 0.1, "recall": 0.2}],
                "algorithms": [
                    {
                        "name": "itemcf",
                        "summary": "Primary recommender",
                        "best_precision": 0.1,
                        "best_recall": 0.2,
                        "best_k": 5,
                        "user_count": 4,
                        "metrics": [{"k": 5, "precision": 0.1, "recall": 0.2}],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(reverse("evaluations:results"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "itemcf" in content
    assert "0.1" in content
    assert "Offline evaluation lab" in content
    assert "K-value checkpoints" in content
    assert "Best precision" in content


def test_load_experiment_summary_returns_empty_for_malformed_json(tmp_path):
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text("{bad json", encoding="utf-8")

    from apps.evaluations.services import load_experiment_summary

    assert load_experiment_summary(tmp_path) == {"overview": [], "algorithms": []}


def test_load_experiment_summary_returns_empty_for_invalid_utf8(tmp_path):
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_bytes(b"\xff\xfe\xfa")

    from apps.evaluations.services import load_experiment_summary

    assert load_experiment_summary(tmp_path) == {"overview": [], "algorithms": []}
