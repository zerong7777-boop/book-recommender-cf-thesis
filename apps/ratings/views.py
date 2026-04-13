from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.catalog.models import Book

from .forms import RatingForm
from .services import delete_rating, upsert_rating


@login_required
def first_rate_view(request):
    books = Book.objects.order_by("-rating_count", "-average_rating")[:12]
    return render(request, "ratings/first_rate.html", {"rating_form": RatingForm(), "books": books})


@login_required
def rate_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            upsert_rating(user=request.user, book=book, score=form.cleaned_data["score"])
            return redirect(reverse("catalog:book_detail", kwargs={"pk": book.pk}))
    else:
        form = RatingForm()
    return render(request, "ratings/rate_book.html", {"book": book, "form": form})


@login_required
def delete_rating_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        delete_rating(user=request.user, book=book)
        return redirect(reverse("accounts:profile"))
    return render(request, "ratings/delete_rating.html", {"book": book})
