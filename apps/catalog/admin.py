from django.contrib import admin

from apps.catalog.models import Book, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "publication_year", "average_rating", "rating_count")
    list_filter = ("category", "publication_year")
    search_fields = ("title", "author", "publisher")
