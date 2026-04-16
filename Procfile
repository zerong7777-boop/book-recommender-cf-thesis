web: python manage.py collectstatic --noinput && gunicorn book_recommender.wsgi:application --bind 0.0.0.0:$PORT
