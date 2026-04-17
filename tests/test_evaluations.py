import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.catalog.models import Book, Category
from apps.evaluations.models import EvaluationRun
from apps.evaluations.services import evaluation_artifact_dir, k_values
from apps.ratings.models import ImportedInteraction, UserRating


TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_testdata"


def make_temp_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{prefix}{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_k_values_match_spec():
    assert k_values() == [5, 10, 20, 30]


@pytest.mark.django_db
def test_evaluate_recommenders_writes_summary(settings):
    tmp_path = make_temp_dir("eval-summary-")
    settings.BASE_DIR = tmp_path

    call_command("evaluate_recommenders")

    summary_path = evaluation_artifact_dir(tmp_path) / "summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert [entry["k"] for entry in payload["overview"]] == [5, 10, 20, 30]
    assert {entry["name"] for entry in payload["algorithms"]} == {"hot", "itemcf", "usercf", "hybrid"}


@pytest.mark.django_db
def test_evaluate_recommenders_computes_non_placeholder_metrics(settings, django_user_model):
    tmp_path = make_temp_dir("eval-metrics-")
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


@pytest.mark.django_db
def test_evaluate_recommenders_uses_imported_interactions_and_persists_runs(settings):
    tmp_path = make_temp_dir("eval-imported-")
    settings.BASE_DIR = tmp_path
    category = Category.objects.create(name="Imported Eval", slug="imported-eval")
    books = [
        Book.objects.create(
            title=f"Imported Book {idx}",
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
    interaction_specs = [
        (200, [books[0], books[1], books[2]]),
        (201, [books[0], books[1], books[3]]),
        (202, [books[0], books[1], books[4]]),
        (203, [books[0], books[2], books[3]]),
    ]
    for dataset_user_id, rated_books in interaction_specs:
        for score, book in enumerate(rated_books, start=3):
            ImportedInteraction.objects.create(
                dataset_user_id=dataset_user_id,
                book=book,
                score=min(score, 5),
            )

    call_command("evaluate_recommenders")

    payload = json.loads((evaluation_artifact_dir(tmp_path) / "summary.json").read_text(encoding="utf-8"))
    assert any(row["precision"] > 0 for row in payload["overview"])
    assert payload["metadata"]["dataset_user_count"] == 4
    assert payload["curves"]["precision"]
    assert payload["case_studies"]
    assert payload["similarity_comparison"]["cosine"]["name"] == "cosine"
    assert payload["similarity_comparison"]["pearson"]["name"] == "pearson"
    assert payload["random_split"]["test_interaction_count"] > 0
    assert payload["random_split"]["algorithms"]
    assert EvaluationRun.objects.count() == 4
    assert {
        run.strategy for run in EvaluationRun.objects.all()
    } == {"hot", "itemcf", "usercf", "hybrid"}


@pytest.mark.django_db
def test_evaluate_recommenders_can_refresh_artifact_without_recording_runs(settings):
    tmp_path = make_temp_dir("eval-skip-record-")
    settings.BASE_DIR = tmp_path
    category = Category.objects.create(name="Skip Record Eval", slug="skip-record-eval")
    books = [
        Book.objects.create(
            title=f"Skip Record Book {idx}",
            author="Author",
            category=category,
            description="desc",
            publisher="pub",
            publication_year=2024,
            average_rating=4.0,
            rating_count=10,
        )
        for idx in range(1, 4)
    ]
    for dataset_user_id in (301, 302):
        for score, book in enumerate(books, start=3):
            ImportedInteraction.objects.create(
                dataset_user_id=dataset_user_id,
                book=book,
                score=min(score, 5),
            )

    call_command("evaluate_recommenders", skip_record=True)

    summary_path = evaluation_artifact_dir(tmp_path) / "summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["overview"]
    assert EvaluationRun.objects.count() == 0


def test_experiment_results_page_reads_summary(client, settings):
    tmp_path = make_temp_dir("eval-view-")
    settings.BASE_DIR = tmp_path
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(
        json.dumps(
            {
                "overview": [{"k": 5, "precision": 0.1, "recall": 0.2}],
                "metadata": {"dataset_user_count": 4, "site_user_count": 1, "run_count": 4},
                "curves": {
                    "precision": [
                        {"name": "itemcf", "points": [{"k": 5, "value": 0.1}]},
                    ],
                    "recall": [
                        {"name": "itemcf", "points": [{"k": 5, "value": 0.2}]},
                    ],
                },
                "case_studies": [
                    {
                        "subject": "dataset:100",
                        "holdout_book": "Book 1",
                        "best_strategy": "itemcf",
                        "top_recommendations": ["Book 2", "Book 3"],
                    }
                ],
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
                "similarity_comparison": {
                    "cosine": {"name": "cosine", "best_precision": 0.1, "best_recall": 0.2, "best_k": 5},
                    "pearson": {"name": "pearson", "best_precision": 0.08, "best_recall": 0.16, "best_k": 5},
                },
                "random_split": {
                    "train_interaction_count": 8,
                    "test_interaction_count": 2,
                    "algorithms": [{"name": "itemcf", "precision": 0.1, "recall": 0.2, "best_k": 5}],
                },
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
    assert "离线评估实验室" in content
    assert "K 值检查点" in content
    assert "最佳精确率" in content
    assert "精确率曲线" in content
    assert "案例分析" in content
    assert "相似度对比" in content
    assert "随机交互划分" in content
    assert "pearson" in content


def test_load_experiment_summary_returns_empty_for_malformed_json():
    tmp_path = make_temp_dir("eval-badjson-")
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text("{bad json", encoding="utf-8")

    from apps.evaluations.services import load_experiment_summary

    assert load_experiment_summary(tmp_path) == {
        "metadata": {},
        "overview": [],
        "algorithms": [],
        "curves": {"precision": [], "recall": []},
        "case_studies": [],
        "similarity_comparison": {},
        "random_split": {"train_interaction_count": 0, "test_interaction_count": 0, "algorithms": []},
    }


def test_load_experiment_summary_returns_empty_for_invalid_utf8():
    tmp_path = make_temp_dir("eval-badutf8-")
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_bytes(b"\xff\xfe\xfa")

    from apps.evaluations.services import load_experiment_summary

    assert load_experiment_summary(tmp_path) == {
        "metadata": {},
        "overview": [],
        "algorithms": [],
        "curves": {"precision": [], "recall": []},
        "case_studies": [],
        "similarity_comparison": {},
        "random_split": {"train_interaction_count": 0, "test_interaction_count": 0, "algorithms": []},
    }
