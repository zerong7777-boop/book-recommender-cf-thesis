import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_user_can_register(client):
    response = client.post(reverse("accounts:register"), {
        "username": "reader",
        "email": "reader@example.com",
        "password1": "ReaderPass123",
        "password2": "ReaderPass123",
    })
    assert response.status_code == 302


@pytest.mark.django_db
def test_user_can_login(client, django_user_model):
    django_user_model.objects.create_user(username="reader2", email="reader2@example.com", password="ReaderPass123")
    response = client.post(reverse("accounts:login"), {
        "username": "reader2",
        "password": "ReaderPass123",
    })
    assert response.status_code == 302
