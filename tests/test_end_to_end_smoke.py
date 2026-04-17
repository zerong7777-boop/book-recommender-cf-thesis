import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse

from apps.evaluations.services import evaluation_artifact_dir, load_experiment_summary
import scripts.init_demo_data as demo_init
from scripts.init_demo_data import initialize_demo_data


@pytest.mark.django_db
def test_thesis_demo_smoke_flow(client):
    cache.clear()
    initialize_demo_data()

    user_model = get_user_model()
    demo_user = user_model.objects.get(username="demo_reader")
    staff_user = user_model.objects.get(username="thesis_admin")

    login_response = client.post(
        reverse("accounts:login"),
        {"username": "demo_reader", "password": "DemoPass123!"},
    )
    assert login_response.status_code == 302

    profile_response = client.get(reverse("accounts:profile"))
    assert profile_response.status_code == 200
    profile_html = profile_response.content.decode()
    assert "demo_reader" in profile_html
    assert "推荐状态" in profile_html
    assert "个性化推荐" in profile_html
    assert profile_html.count("/5") >= 3

    recommendations_response = client.get(reverse("recommendations:list"))
    assert recommendations_response.status_code == 200
    recommendations_html = recommendations_response.content.decode()
    assert "<h1 class=\"page-title\">推荐中心</h1>" in recommendations_html
    assert (
        "ItemCF 数据过稀时采用热门回退" in recommendations_html
        or "与你的评分相似" in recommendations_html
    )
    assert "demo reader" not in recommendations_html.lower()

    client.logout()
    staff_login_response = client.post(
        reverse("accounts:login"),
        {"username": "thesis_admin", "password": "AdminPass123!"},
    )
    assert staff_login_response.status_code == 302

    dashboard_response = client.get(reverse("dashboard:home"))
    assert dashboard_response.status_code == 200
    dashboard_html = dashboard_response.content.decode()
    assert "运维总览" in dashboard_html
    assert "手动触发刷新" in dashboard_html
    assert "rebuild_recommendations" in dashboard_html

    assert demo_user.is_staff is False
    assert staff_user.is_staff is True
    cache.clear()


@pytest.mark.django_db
def test_initialize_demo_data_keeps_seeded_data_when_rebuild_fails(monkeypatch):
    def fail_rebuild(*, top_k):
        raise RuntimeError("rebuild failed")

    monkeypatch.setattr(demo_init, "rebuild_recommendations_for_all_users", fail_rebuild, raising=False)

    with pytest.raises(RuntimeError, match="rebuild failed"):
        initialize_demo_data()

    user_model = get_user_model()
    assert user_model.objects.filter(username="thesis_admin", is_staff=True, is_superuser=True).exists()
    assert user_model.objects.filter(username="demo_reader", is_staff=False).exists()
    demo_user = user_model.objects.get(username="demo_reader")
    assert demo_user.ratings.count() == 3


@pytest.mark.django_db
def test_initialize_demo_data_reports_reruns_honestly_and_returns_rebuild_job(monkeypatch):
    rebuild_calls = []
    fake_job = object()

    def fake_rebuild(*, top_k):
        rebuild_calls.append(top_k)
        return fake_job

    monkeypatch.setattr(demo_init, "rebuild_recommendations_for_all_users", fake_rebuild, raising=False)

    first_result = initialize_demo_data()
    second_result = initialize_demo_data()

    assert first_result["ratings_created"] == 3
    assert first_result["ratings_updated"] == 0
    assert first_result["rebuild_job"] is fake_job
    assert second_result["ratings_created"] == 0
    assert second_result["ratings_updated"] == 3
    assert second_result["rebuild_job"] is fake_job
    assert rebuild_calls == [10, 10]


@pytest.mark.django_db
def test_initialize_demo_data_supports_non_zero_evaluation_metrics(settings, tmp_path):
    settings.BASE_DIR = tmp_path

    initialize_demo_data()
    call_command("evaluate_recommenders")

    summary = load_experiment_summary(tmp_path)

    assert any(row["precision"] > 0 for row in summary["overview"])
    assert evaluation_artifact_dir(tmp_path).joinpath("summary.json").exists()
