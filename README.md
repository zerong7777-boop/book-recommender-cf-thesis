# book-recommender-cf

Minimal Django scaffold for the book recommender thesis project.

## Setup

1. Copy `.env.example` to `.env` and set local secrets.
2. Install dependencies with `conda run -n bookrec311 python -m pip install -r requirements.txt`.
3. Run `conda run -n bookrec311 python manage.py check` after the database and Redis services are available.
