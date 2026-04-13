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
    assert "success" in content


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
    (runtime_dir / "dashboard_rebuild.lock").write_text("locked", encoding="utf-8")
    client.login(username="locked", password="AdminPass123")
    response = client.post(reverse("dashboard:trigger_rebuild"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert called["launched"] is False
