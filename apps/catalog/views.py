from django.shortcuts import get_object_or_404, render

from apps.recommendations.selectors import homepage_recommendation_block, similar_books_for_detail

from .models import Book, Category
from .services import homepage_categories, search_books


def home_view(request):
    recommendation_block = homepage_recommendation_block(request.user)
    return render(
        request,
        "catalog/home.html",
        {"recommendation_block": recommendation_block, "categories": homepage_categories()},
    )


def book_list_view(request):
    query = request.GET.get("q", "").strip()
    books = search_books(query)
    return render(request, "catalog/book_list.html", {"books": books, "query": query})


def category_list_view(request, slug):
    category = get_object_or_404(Category, slug=slug)
    return render(
        request,
        "catalog/category_list.html",
        {"category": category, "books": category.books.select_related("category")},
    )


def book_detail_view(request, pk):
    book = get_object_or_404(Book.objects.select_related("category"), pk=pk)
    return render(
        request,
        "catalog/book_detail.html",
        {"book": book, "similar_books": similar_books_for_detail(book, request.user)},
    )
