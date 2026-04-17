import pytest
from django.urls import reverse

from apps.catalog.models import Book, Category


@pytest.mark.django_db
def test_homepage_loads(client):
    response = client.get(reverse("catalog:home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_homepage_shows_primary_navigation_entry_points(client):
    response = client.get(reverse("catalog:home"))

    content = response.content.decode()

    assert "浏览图书" in content
    assert "登录" in content
    assert reverse("catalog:book_list") in content


@pytest.mark.django_db
def test_homepage_highlights_book_discovery_sections(client):
    response = client.get(reverse("catalog:home"))

    content = response.content.decode()

    assert "发现下一本想读的书" in content
    assert "浏览分类" in content
    assert "推荐精选" in content


@pytest.mark.django_db
def test_homepage_surfaces_demo_paths_and_experiment_entry(client):
    response = client.get(reverse("catalog:home"))

    content = response.content.decode()

    assert "两个演示路径" in content
    assert "实验依据" in content
    assert reverse("evaluations:results") in content


@pytest.mark.django_db
def test_book_list_page_shows_chinese_copy(client):
    response = client.get(reverse("catalog:book_list"))

    content = response.content.decode()

    assert "图书列表" in content
    assert "按书名或作者搜索" in content
    assert "搜索目录" in content


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


@pytest.mark.django_db
def test_search_filters_books_by_author(client):
    category = Category.objects.create(name="Fantasy", slug="fantasy")
    Book.objects.create(
        title="Magic Book",
        author="Alice Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
    )
    Book.objects.create(
        title="History Book",
        author="Bob Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2021,
    )
    response = client.get(reverse("catalog:book_list"), {"q": "Alice"})
    content = response.content.decode()
    assert "Magic Book" in content
    assert "History Book" not in content


@pytest.mark.django_db
def test_category_page_renders_expected_book(client):
    category = Category.objects.create(name="Fantasy", slug="fantasy")
    book = Book.objects.create(
        title="Magic Book",
        author="Alice Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
    )

    response = client.get(reverse("catalog:category_list", kwargs={"slug": category.slug}))

    assert response.status_code == 200
    content = response.content.decode()
    assert book.title in content
    assert book.author in content


@pytest.mark.django_db
def test_book_detail_page_renders_selected_book(client):
    category = Category.objects.create(name="Fantasy", slug="fantasy")
    book = Book.objects.create(
        title="Magic Book",
        author="Alice Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2020,
    )

    response = client.get(reverse("catalog:book_detail", kwargs={"pk": book.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert book.title in content
    assert book.author in content


@pytest.mark.django_db
def test_missing_category_returns_404(client):
    response = client.get(reverse("catalog:category_list", kwargs={"slug": "missing"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_book_returns_404(client):
    response = client.get(reverse("catalog:book_detail", kwargs={"pk": 999999}))
    assert response.status_code == 404
