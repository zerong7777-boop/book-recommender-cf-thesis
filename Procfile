web: python manage.py collectstatic --noinput && python manage.py evaluate_recommenders --skip-record && gunicorn book_recommender.wsgi:application --bind 0.0.0.0:$PORT
