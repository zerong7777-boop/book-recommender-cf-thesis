# book-recommender-cf

Django thesis project for a local book recommender demo.

## Prerequisites

1. Python environment: `bookrec311`
2. Database: MySQL 8.x or compatible
3. Cache: Redis 6.x or compatible

## Environment setup

1. Copy `.env.example` to `.env` in the project root.
2. Set the MySQL and Redis values for your local machine.
3. Keep `DJANGO_DEBUG=True` for local development unless you are explicitly testing production-style settings.

Example `.env` values:

```env
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
MYSQL_DATABASE=book_recommender_cf
MYSQL_USER=root
MYSQL_PASSWORD=replace-me
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
REDIS_URL=redis://127.0.0.1:6379/1
```

## Install dependencies

```powershell
conda run -n bookrec311 python -m pip install -r requirements.txt
```

## Database setup

Run migrations after MySQL is available:

```powershell
conda run -n bookrec311 python manage.py migrate
```

If you already have a Goodbooks import or another local catalog load step, run that first. This repository does not ship a dedicated Goodbooks import command. For a self-contained smoke/demo setup, the demo initializer below seeds a compact sample catalog automatically.

## Demo data

Seed the thesis demo account, staff admin account, sample catalog, ratings, and recommendation cache:

```powershell
conda run -n bookrec311 python scripts/init_demo_data.py
```

The initializer creates:

1. Staff admin: `thesis_admin` / `AdminPass123!`
2. Demo reader: `demo_reader` / `DemoPass123!`
3. At least 3 ratings for the demo reader
4. A compact sample catalog suitable for smoke validation

If you already loaded a catalog and only want the accounts plus ratings, run:

```powershell
conda run -n bookrec311 python scripts/init_demo_data.py --no-sample-catalog
```

## Recommendation rebuild

Rebuild collaborative-filtering and hot-start recommendation data:

```powershell
conda run -n bookrec311 python manage.py rebuild_recommendations
```

## Evaluation

Generate the thesis evaluation artifact summary:

```powershell
conda run -n bookrec311 python manage.py evaluate_recommenders
```

## Start the app

```powershell
conda run -n bookrec311 python manage.py runserver
```

## Demo flow

1. Open the site in the browser.
2. Log in as `demo_reader` with `DemoPass123!`.
3. Open the profile page to see the seeded ratings and personalized recommendation state.
4. Open the recommendations page to review the current recommendation payload.
5. Log out and log in as `thesis_admin` with `AdminPass123!`.
6. Open the dashboard to inspect the latest offline job and trigger a rebuild.

## Verification

Before wrapping up a local change, run:

```powershell
conda run -n bookrec311 python manage.py check
conda run -n bookrec311 pytest tests/test_end_to_end_smoke.py -q
```
