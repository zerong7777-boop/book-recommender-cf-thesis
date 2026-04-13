import json

from django.core.management import call_command
from django.urls import reverse

from apps.evaluations.services import evaluation_artifact_dir, k_values


def test_k_values_match_spec():
    assert k_values() == [5, 10, 20, 30]


def test_evaluate_recommenders_writes_summary(settings, tmp_path):
    settings.BASE_DIR = tmp_path

    call_command("evaluate_recommenders")

    summary_path = evaluation_artifact_dir(tmp_path) / "summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert [entry["k"] for entry in payload["overview"]] == [5, 10, 20, 30]


def test_experiment_results_page_reads_summary(client, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(
        json.dumps(
            {
                "overview": [{"k": 5, "precision": 0.1, "recall": 0.2}],
                "algorithms": [{"name": "itemcf", "summary": "Primary recommender"}],
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
