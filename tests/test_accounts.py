import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Book, Category
from apps.ratings.models import UserRating
from apps.recommendations.cache import user_recommendation_cache_key


@pytest.mark.django_db
def test_user_can_register(client, django_user_model):
    response = client.post(reverse("accounts:register"), {
        "username": "reader",
        "email": "reader@example.com",
        "password1": "ReaderPass123",
        "password2": "ReaderPass123",
    })
    user = django_user_model.objects.get(username="reader")

    assert user.email == "reader@example.com"
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:profile")
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_user_can_login(client, django_user_model):
    django_user_model.objects.create_user(username="reader2", email="reader2@example.com", password="ReaderPass123")
    response = client.post(reverse("accounts:login"), {
        "username": "reader2",
        "password": "ReaderPass123",
    })
    assert response.status_code == 302
    assert client.get(reverse("accounts:profile")).status_code == 200


@pytest.mark.django_db
def test_profile_links_to_first_rating_flow(client, django_user_model):
    django_user_model.objects.create_user(username="reader3", email="reader3@example.com", password="ReaderPass123")
    client.login(username="reader3", password="ReaderPass123")

    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 200
    assert reverse("ratings:first-rate") in response.content.decode()


@pytest.mark.django_db
def test_profile_page_shows_navigation_to_recommendations(client, django_user_model):
    django_user_model.objects.create_user(username="reader4", email="reader4@example.com", password="ReaderPass123")
    client.login(username="reader4", password="ReaderPass123")

    response = client.get(reverse("accounts:profile"))

    content = response.content.decode()

    assert reverse("recommendations:list") in content
    assert "推荐中心" in content


@pytest.mark.django_db
def test_profile_page_shows_recommendation_reason_preview(client, django_user_model):
    cache.clear()
    user = django_user_model.objects.create_user(username="reader5", email="reader5@example.com", password="ReaderPass123")
    category = Category.objects.create(name="Preview", slug="preview")
    rated_books = [
        Book.objects.create(
            title=f"Rated {idx}",
            author="Author",
            category=category,
            description="desc",
            publisher="pub",
            publication_year=2024,
            average_rating=4.2,
            rating_count=12,
        )
        for idx in range(1, 4)
    ]
    recommended = Book.objects.create(
        title="Preview Pick",
        author="Author",
        category=category,
        description="desc",
        publisher="pub",
        publication_year=2024,
        average_rating=4.4,
        rating_count=18,
    )
    for book in rated_books:
        UserRating.objects.create(user=user, book=book, score=5)
    cache.set(
        user_recommendation_cache_key(user.id),
        {
            "generated_at": timezone.now().isoformat(),
            "strategy": "itemcf",
            "items": [
                {
                    "book_id": recommended.id,
                    "title": recommended.title,
                    "author": recommended.author,
                    "category": category.name,
                    "category_slug": category.slug,
                    "cover_url": recommended.cover_url,
                    "average_rating": float(recommended.average_rating),
                    "reason": "Because you liked Rated 1",
                    "rank": 1,
                }
            ],
        },
        timeout=None,
    )

    client.login(username="reader5", password="ReaderPass123")
    response = client.get(reverse("accounts:profile"))

    content = response.content.decode()
    assert "推荐原因" in content
    assert "Preview Pick" in content
    assert "Because you liked Rated 1" in content


@pytest.mark.django_db
def test_password_change_page_uses_chinese_labels(client, django_user_model):
    django_user_model.objects.create_user(username="reader6", email="reader6@example.com", password="ReaderPass123")
    client.login(username="reader6", password="ReaderPass123")

    response = client.get(reverse("accounts:password_change"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "修改密码" in content
    assert "当前密码" in content
    assert "新密码" in content
    assert "确认新密码" in content
    assert "返回个人中心" in content
