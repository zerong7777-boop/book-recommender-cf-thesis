import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.evaluations.services import evaluation_artifact_dir, k_values


class Command(BaseCommand):
    help = "Generate offline recommendation evaluation artifacts"

    def handle(self, *args, **options):
        artifact_dir = evaluation_artifact_dir(settings.BASE_DIR)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "overview": [{"k": k, "precision": 0.0, "recall": 0.0} for k in k_values()],
            "algorithms": [
                {"name": "hot", "summary": "Cold-start baseline using popularity signals."},
                {"name": "itemcf", "summary": "Primary offline-to-online collaborative filtering strategy."},
                {"name": "usercf", "summary": "Offline comparison baseline for thesis evaluation."},
                {"name": "hybrid", "summary": "Lightweight metadata-assisted comparison strategy."},
            ],
        }
        (artifact_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("evaluation artifacts generated"))
