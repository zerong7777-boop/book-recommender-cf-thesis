from django.contrib import admin

from apps.ratings.models import ImportedInteraction, UserRating, UserRatingHistory


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


@admin.register(ImportedInteraction)
class ImportedInteractionAdmin(admin.ModelAdmin):
    list_display = ("dataset_name", "dataset_user_id", "book", "score", "imported_at")
    list_filter = ("dataset_name", "score")
    search_fields = ("book__title",)
