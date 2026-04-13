import pytest
from django.urls import reverse

from apps.catalog.models import Book, Category


@pytest.mark.django_db
def test_homepage_loads(client):
    response = client.get(reverse("catalog:home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_search_filters_books_by_title(client):
    category = Category.objects.create(name="Fantasy", slug="fantasy")
    Book.objects.create(
        title="Magic Book",
        author="A",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
    )
    Book.objects.create(
        title="History Book",
        author="B",
        category=category,
        description="d",
        publisher="p",
        publication_year=2021,
    )
    response = client.get(reverse("catalog:book_list"), {"q": "Magic"})
    assert "Magic Book" in response.content.decode()
    assert "History Book" not in response.content.decode()
