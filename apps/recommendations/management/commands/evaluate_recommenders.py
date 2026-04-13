import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.evaluations.services import evaluation_artifact_dir, generate_evaluation_summary


class Command(BaseCommand):
    help = "Generate offline recommendation evaluation artifacts"

    def handle(self, *args, **options):
        artifact_dir = evaluation_artifact_dir(settings.BASE_DIR)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        summary = generate_evaluation_summary()
        (artifact_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("evaluation artifacts generated"))
