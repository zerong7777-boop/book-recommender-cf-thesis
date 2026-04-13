from apps.recommendations.models import SimilarBookResult


def recommendation_state_for_user(user):
    if not user.is_authenticated:
        return "hot"
    if user.ratings.count() < 3:
        return "cold-start"
    return "personalized"


def homepage_recommendation_block(user):
    return {
        "state": recommendation_state_for_user(user),
        "items": [],
    }


def similar_books_for_detail(book, user):
    return [
        result.target_book
        for result in SimilarBookResult.objects.filter(source_book=book).select_related("target_book__category")
    ]
