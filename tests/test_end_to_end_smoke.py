import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scripts.init_demo_data import initialize_demo_data


@pytest.mark.django_db
def test_thesis_demo_smoke_flow(client):
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
    assert "Recommendation state: personalized" in profile_html
    assert profile_html.count("btn btn-sm btn-outline-danger") >= 3

    recommendations_response = client.get(reverse("recommendations:list"))
    assert recommendations_response.status_code == 200
    recommendations_html = recommendations_response.content.decode()
    assert "Recommendation Results" in recommendations_html
    assert "Popular fallback because ItemCF had sparse data" in recommendations_html
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
    assert "Dashboard" in dashboard_html
    assert "rebuild_recommendations" in dashboard_html

    assert demo_user.is_staff is False
    assert staff_user.is_staff is True
