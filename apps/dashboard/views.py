import threading
from pathlib import Path

from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.core.management import call_command
from django.shortcuts import redirect, render

from apps.recommendations.models import OfflineJobRun, RecommendationResult

REBUILD_LOCK_FILENAME = "dashboard_rebuild.lock"


def _rebuild_lock_path() -> Path:
    runtime_dir = Path(settings.BASE_DIR) / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / REBUILD_LOCK_FILENAME


def _acquire_rebuild_lock() -> bool:
    try:
        _rebuild_lock_path().open("x", encoding="utf-8").close()
    except FileExistsError:
        return False
    return True


def _release_rebuild_lock() -> None:
    _rebuild_lock_path().unlink(missing_ok=True)


def _rebuild_in_progress() -> bool:
    return _rebuild_lock_path().exists()


def _run_rebuild_job():
    try:
        call_command("rebuild_recommendations")
    finally:
        _release_rebuild_lock()


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
            "rebuild_in_progress": _rebuild_in_progress(),
        },
    )


@staff_member_required
def trigger_rebuild_view(request):
    if request.method == "POST" and _acquire_rebuild_lock():
        _launch_rebuild_job()
    return redirect("dashboard:home")
