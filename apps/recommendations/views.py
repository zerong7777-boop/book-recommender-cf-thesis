from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .selectors import recommendation_block_for_user


@login_required
def recommendation_list_view(request):
    return render(
        request,
        "recommendations/recommendation_list.html",
        {"recommendation_block": recommendation_block_for_user(request.user)},
    )
