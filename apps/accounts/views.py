from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.accounts.forms import LocalizedPasswordChangeForm, LoginForm, RegistrationForm
from apps.ratings.models import UserRating
from apps.recommendations.selectors import recommendation_preview_for_user, recommendation_state_for_user


def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("accounts:profile")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class UserLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


@login_required
def profile_view(request):
    ratings = UserRating.objects.filter(user=request.user).select_related("book").order_by("-rated_at")
    recommendation_state = recommendation_state_for_user(request.user)
    recommendation_preview = recommendation_preview_for_user(request.user)
    return render(
        request,
        "accounts/profile.html",
        {
            "ratings": ratings,
            "recommendation_state": recommendation_state,
            "recommendation_preview": recommendation_preview,
        },
    )


class UserPasswordChangeView(PasswordChangeView):
    form_class = LocalizedPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    template_name = "accounts/password_change.html"
