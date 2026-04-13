import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.recommendations.models import OfflineJobRun, RecommendationResult


@pytest.mark.django_db
def test_dashboard_requires_staff(client):
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 302


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
def test_staff_can_trigger_rebuild(client, monkeypatch):
    staff = get_user_model().objects.create_user(
        username="operator",
        email="operator@example.com",
        password="AdminPass123",
        is_staff=True,
    )
    called = {}

    def fake_call_command(name):
        called["name"] = name

    monkeypatch.setattr("apps.dashboard.views.call_command", fake_call_command)

    client.login(username="operator", password="AdminPass123")
    response = client.post(reverse("dashboard:trigger_rebuild"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert called["name"] == "rebuild_recommendations"
