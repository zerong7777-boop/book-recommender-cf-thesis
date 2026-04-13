import json
from pathlib import Path


def k_values():
    return [5, 10, 20, 30]


def evaluation_artifact_dir(base_dir: Path):
    return base_dir / "artifacts" / "evaluations"


def load_experiment_summary(base_dir: Path):
    summary_path = evaluation_artifact_dir(base_dir) / "summary.json"
    if not summary_path.exists():
        return {"overview": [], "algorithms": []}
    return json.loads(summary_path.read_text(encoding="utf-8"))
