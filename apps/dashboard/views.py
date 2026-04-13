import threading

from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.management import call_command
from django.shortcuts import redirect, render

from apps.recommendations.models import OfflineJobRun, RecommendationResult

REBUILD_LOCK_KEY = "dashboard:rebuild-lock"
REBUILD_LOCK_TIMEOUT_SECONDS = 30 * 60


def _run_rebuild_job():
    try:
        call_command("rebuild_recommendations")
    finally:
        cache.delete(REBUILD_LOCK_KEY)


def _launch_rebuild_job():
    threading.Thread(target=_run_rebuild_job, daemon=True).start()


@staff_member_required
def dashboard_home_view(request):
    return render(
        request,
        "dashboard/home.html",
        {
            "latest_job": OfflineJobRun.objects.order_by("-started_at").first(),
            "latest_results": RecommendationResult.objects.select_related("user").order_by("-generated_at")[:10],
            "rebuild_in_progress": cache.get(REBUILD_LOCK_KEY) is not None,
        },
    )


@staff_member_required
def trigger_rebuild_view(request):
    if request.method == "POST" and cache.add(REBUILD_LOCK_KEY, "1", timeout=REBUILD_LOCK_TIMEOUT_SECONDS):
        _launch_rebuild_job()
    return redirect("dashboard:home")
