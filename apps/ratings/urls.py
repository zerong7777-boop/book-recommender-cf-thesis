from django.urls import path

from .views import delete_rating_view, first_rate_view, rate_book_view

app_name = "ratings"

urlpatterns = [
    path("first-rate/", first_rate_view, name="first-rate"),
    path("rate-book/<int:pk>/", rate_book_view, name="rate-book"),
    path("delete-rating/<int:pk>/", delete_rating_view, name="delete-rating"),
]

