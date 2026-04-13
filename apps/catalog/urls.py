from django.urls import path

from .views import book_detail_view, book_list_view, category_list_view, home_view

app_name = "catalog"

urlpatterns = [
    path("", home_view, name="home"),
    path("books/", book_list_view, name="book_list"),
    path("books/<int:pk>/", book_detail_view, name="book_detail"),
    path("categories/<slug:slug>/", category_list_view, name="category_list"),
]

