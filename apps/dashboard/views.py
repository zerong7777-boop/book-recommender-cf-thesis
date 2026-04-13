from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import redirect, render

from apps.recommendations.models import OfflineJobRun, RecommendationResult


@staff_member_required
def dashboard_home_view(request):
    return render(
        request,
        "dashboard/home.html",
        {
            "latest_job": OfflineJobRun.objects.order_by("-started_at").first(),
            "latest_results": RecommendationResult.objects.order_by("-generated_at")[:10],
        },
    )


@staff_member_required
def trigger_rebuild_view(request):
    if request.method == "POST":
        call_command("rebuild_recommendations")
    return redirect("dashboard:home")
