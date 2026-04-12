def recommendation_state_for_user(user):
    if not user.is_authenticated:
        return "hot"
    if user.ratings.count() < 3:
        return "cold-start"
    return "personalized"
