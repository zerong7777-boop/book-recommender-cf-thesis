import json
import os

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.recommendations.models import OfflineJobRun, RecommendationResult
from pathlib import Path


@pytest.mark.django_db
def test_dashboard_requires_staff(client):
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_non_staff_user_cannot_open_dashboard_or_trigger_rebuild(client):
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        password="ReaderPass123",
        is_staff=False,
    )

    client.login(username="reader", password="ReaderPass123")
    home_response = client.get(reverse("dashboard:home"))
    trigger_response = client.post(reverse("dashboard:trigger_rebuild"))

    assert home_response.status_code == 302
    assert trigger_response.status_code == 302


@pytest.mark.django_db
def test_staff_dashboard_shows_latest_job(client):
    staff = get_user_model().objects.create_user(
        username="admin",
        email="admin@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    OfflineJobRun.objects.create(
        job_name="rebuild_recommendations",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        processed_user_count=5,
        summary="processed 5 users",
    )
    RecommendationResult.objects.create(strategy="hot", generated_at=timezone.now(), top_k=20)

    client.login(username="admin", password="AdminPass123")
    response = client.get(reverse("dashboard:home"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "rebuild_recommendations" in content
    assert "成功" in content


@pytest.mark.django_db
def test_staff_dashboard_shows_ops_summary_cards(client):
    staff = get_user_model().objects.create_user(
        username="ops",
        email="ops@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    OfflineJobRun.objects.create(
        job_name="rebuild_recommendations",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        processed_user_count=8,
        summary="processed 8 users",
    )

    client.login(username="ops", password="AdminPass123")
    response = client.get(reverse("dashboard:home"))

    content = response.content.decode()
    assert "运维总览" in content
    assert "手动触发刷新" in content
    assert "最近推荐结果" in content


@pytest.mark.django_db
def test_staff_dashboard_clears_stale_lock_from_home(client, monkeypatch, settings, tmp_path):
    staff = get_user_model().objects.create_user(
        username="cleanup",
        email="cleanup@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    settings.BASE_DIR = tmp_path
    runtime_dir = Path(tmp_path) / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "dashboard_rebuild.lock").write_text(
        json.dumps({"pid": 999999, "created_at": 0.0}),
        encoding="utf-8",
    )

    client.login(username="cleanup", password="AdminPass123")
    response = client.get(reverse("dashboard:home"))

    assert response.status_code == 200
    assert "当前已有刷新任务正在运行。" not in response.content.decode()
    assert not (runtime_dir / "dashboard_rebuild.lock").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific process probe behavior")
def test_process_exists_on_windows_does_not_use_os_kill(monkeypatch):
    import apps.dashboard.views as dashboard_views

    def fail_if_called(pid, signal):
        raise AssertionError("os.kill(pid, 0) can terminate processes on Windows")

    monkeypatch.setattr(dashboard_views.os, "kill", fail_if_called)

    assert dashboard_views._process_exists(os.getpid()) is True


@pytest.mark.django_db
def test_staff_can_trigger_rebuild(client, monkeypatch, settings, tmp_path):
    staff = get_user_model().objects.create_user(
        username="operator",
        email="operator@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    called = {}

    def fake_launch():
        called["launched"] = True

    monkeypatch.setattr("apps.dashboard.views._launch_rebuild_job", fake_launch)
    settings.BASE_DIR = tmp_path

    client.login(username="operator", password="AdminPass123")
    response = client.post(reverse("dashboard:trigger_rebuild"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert called["launched"] is True


@pytest.mark.django_db
def test_trigger_rebuild_skips_launch_when_lock_exists(client, monkeypatch, settings, tmp_path):
    staff = get_user_model().objects.create_user(
        username="locked",
        email="locked@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    called = {"launched": False}

    def fake_launch():
        called["launched"] = True

    monkeypatch.setattr("apps.dashboard.views._launch_rebuild_job", fake_launch)
    settings.BASE_DIR = tmp_path
    runtime_dir = Path(tmp_path) / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    import apps.dashboard.views as dashboard_views

    monkeypatch.setattr(dashboard_views.time, "time", lambda: 9999999999.0)
    (runtime_dir / "dashboard_rebuild.lock").write_text(
        json.dumps({"pid": os.getpid(), "created_at": 0.0}),
        encoding="utf-8",
    )
    client.login(username="locked", password="AdminPass123")
    response = client.post(reverse("dashboard:trigger_rebuild"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert called["launched"] is False


@pytest.mark.django_db
def test_trigger_rebuild_reclaims_stale_lock(client, monkeypatch, settings, tmp_path):
    staff = get_user_model().objects.create_user(
        username="stale",
        email="stale@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    called = {"launched": False}

    def fake_launch():
        called["launched"] = True

    monkeypatch.setattr("apps.dashboard.views._launch_rebuild_job", fake_launch)
    settings.BASE_DIR = tmp_path
    runtime_dir = Path(tmp_path) / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "dashboard_rebuild.lock").write_text(
        json.dumps({"pid": 999999, "created_at": 0.0}),
        encoding="utf-8",
    )
    import apps.dashboard.views as dashboard_views

    monkeypatch.setattr(dashboard_views.time, "time", lambda: 9999999999.0)

    client.login(username="stale", password="AdminPass123")
    response = client.post(reverse("dashboard:trigger_rebuild"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert called["launched"] is True
