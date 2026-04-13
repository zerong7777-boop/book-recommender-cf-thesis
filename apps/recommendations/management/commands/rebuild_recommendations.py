from django.core.management.base import BaseCommand

from apps.recommendations.services import rebuild_recommendations_for_all_users


class Command(BaseCommand):
    help = "Rebuild offline recommendations and cache payloads."

    def add_arguments(self, parser):
        parser.add_argument("--top-k", type=int, default=20)

    def handle(self, *args, **options):
        top_k = options["top_k"]
        job = rebuild_recommendations_for_all_users(top_k=top_k)
        summary = job.summary or ""
        message = (
            f"Recommendations rebuilt: status={job.status}, "
            f"processed_users={job.processed_user_count}, {summary}"
        )
        self.stdout.write(self.style.SUCCESS(message))
