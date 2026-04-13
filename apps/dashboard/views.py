import json
import os
import threading
import time
from pathlib import Path

from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.core.management import call_command
from django.shortcuts import redirect, render

from apps.recommendations.models import OfflineJobRun, RecommendationResult

REBUILD_LOCK_FILENAME = "dashboard_rebuild.lock"
REBUILD_LOCK_TIMEOUT_SECONDS = 30 * 60


def _rebuild_lock_path() -> Path:
    runtime_dir = Path(settings.BASE_DIR) / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / REBUILD_LOCK_FILENAME


def _create_rebuild_lock(lock_path: Path) -> None:
    with lock_path.open("x", encoding="utf-8") as lock_file:
        json.dump({"pid": os.getpid(), "created_at": time.time()}, lock_file)


def _read_rebuild_lock(lock_path: Path):
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        created_at = float(payload.get("created_at", 0.0))
    except (TypeError, ValueError):
        created_at = 0.0
    try:
        pid = int(payload["pid"]) if "pid" in payload else None
    except (TypeError, ValueError):
        pid = None
    return {"pid": pid, "created_at": created_at}


def _windows_process_exists(pid: int) -> bool:
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = ctypes.wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

    process_query_limited_information = 0x1000
    error_access_denied = 5
    still_active = 259

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ctypes.get_last_error() == error_access_denied
    try:
        exit_code = ctypes.wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _process_exists(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _rebuild_lock_is_stale(lock_path: Path) -> bool:
    payload = _read_rebuild_lock(lock_path)
    if payload is None:
        return True
    if payload["pid"] is not None:
        return not _process_exists(payload["pid"])
    return time.time() - payload["created_at"] > REBUILD_LOCK_TIMEOUT_SECONDS


def _acquire_rebuild_lock() -> bool:
    lock_path = _rebuild_lock_path()
    try:
        _create_rebuild_lock(lock_path)
        return True
    except FileExistsError:
        if _rebuild_lock_is_stale(lock_path):
            lock_path.unlink(missing_ok=True)
            try:
                _create_rebuild_lock(lock_path)
                return True
            except FileExistsError:
                return False
        return False


def _release_rebuild_lock() -> None:
    _rebuild_lock_path().unlink(missing_ok=True)


def _rebuild_in_progress() -> bool:
    lock_path = _rebuild_lock_path()
    if not lock_path.exists():
        return False
    if _rebuild_lock_is_stale(lock_path):
        lock_path.unlink(missing_ok=True)
        return False
    return True


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
