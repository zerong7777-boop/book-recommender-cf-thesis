import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.evaluations.services import (
    evaluation_artifact_dir,
    generate_evaluation_summary,
    record_evaluation_runs,
)


class Command(BaseCommand):
    help = "Generate offline recommendation evaluation artifacts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-record",
            action="store_true",
            help="Write summary.json without adding EvaluationRun rows.",
        )

    def handle(self, *args, **options):
        artifact_dir = evaluation_artifact_dir(settings.BASE_DIR)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        summary = generate_evaluation_summary()
        if not options["skip_record"]:
            record_evaluation_runs(summary)
        (artifact_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("evaluation artifacts generated"))
