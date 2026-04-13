from django.db.models import Q

from apps.catalog.models import Book, Category


def search_books(query: str):
    queryset = Book.objects.select_related("category").all()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(author__icontains=query))
    return queryset


def homepage_categories(limit: int = 6):
    return Category.objects.order_by("name")[:limit]
