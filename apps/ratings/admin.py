from django.contrib import admin

from apps.ratings.models import UserRating, UserRatingHistory


@admin.register(UserRating)
class UserRatingAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "score", "rated_at")
    list_filter = ("score", "rated_at")
    search_fields = ("user__username", "book__title")


@admin.register(UserRatingHistory)
class UserRatingHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "score", "action", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "book__title")
