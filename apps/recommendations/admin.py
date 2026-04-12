from django.contrib import admin

from apps.recommendations.models import (
    OfflineJobRun,
    RecommendationItem,
    RecommendationResult,
    SimilarBookResult,
)


class RecommendationItemInline(admin.TabularInline):
    model = RecommendationItem
    extra = 0


@admin.register(OfflineJobRun)
class OfflineJobRunAdmin(admin.ModelAdmin):
    list_display = ("job_name", "status", "started_at", "finished_at", "processed_user_count")
    list_filter = ("status",)
    search_fields = ("job_name",)


@admin.register(RecommendationResult)
class RecommendationResultAdmin(admin.ModelAdmin):
    list_display = ("user", "strategy", "generated_at", "top_k")
    list_filter = ("strategy", "generated_at")
    search_fields = ("user__username",)
    inlines = (RecommendationItemInline,)


@admin.register(RecommendationItem)
class RecommendationItemAdmin(admin.ModelAdmin):
    list_display = ("result", "book", "rank", "score")
    list_filter = ("rank",)
    search_fields = ("book__title",)


@admin.register(SimilarBookResult)
class SimilarBookResultAdmin(admin.ModelAdmin):
    list_display = ("source_book", "target_book", "rank", "score")
    list_filter = ("rank",)
    search_fields = ("source_book__title", "target_book__title")
