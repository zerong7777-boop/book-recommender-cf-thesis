# Book Recommender CF Thesis Demo

A deployable Django book recommendation system built for thesis demos, client walkthroughs, and reviewer-facing presentations. It combines catalog browsing, user ratings, collaborative filtering recommendations, offline evaluation metrics, and an admin operations dashboard in one live web app.

Live demo:

https://web-production-7e7f.up.railway.app

Demo accounts:

| Role | Username | Password | Use case |
| --- | --- | --- | --- |
| Reader | `demo_reader` | `DemoPass123!` | Browse books, rate books, and inspect recommendations |
| Admin | `thesis_admin` | `AdminPass123!` | Open the dashboard, trigger rebuilds, and access Django Admin |

## Screenshots

### Home

The home page introduces the public demo flow and gives visitors direct access to browsing and evaluation results.

![Home page](docs/assets/readme/home.png)

### Login

The login page supports both reader and admin demo paths.

![Login page](docs/assets/readme/login.png)

### Catalog

The catalog page displays the imported book collection and gives the demo enough real content to feel complete.

![Catalog page](docs/assets/readme/catalog.png)

### Evaluation Results

The experiment page shows real offline evaluation output, including K checkpoints, precision, recall, similarity comparison, and random interaction split metrics.

![Evaluation results page](docs/assets/readme/experiments.png)

## What This Project Demonstrates

- A complete Django web app for a book recommendation workflow.
- Reader accounts, login, registration, profile pages, and rating history.
- Book catalog browsing, detail pages, category entry points, and search.
- Recommendation results with scores and human-readable explanations.
- Goodbooks-style public data import through `ImportedInteraction` records.
- Hot recommendation, ItemCF, UserCF, and lightweight hybrid recommendation strategies.
- Offline evaluation artifacts rendered as a thesis-friendly experiment page.
- Admin dashboard for rebuild status, manual refresh, and Django Admin access.
- Railway deployment so reviewers can use a public URL instead of configuring a local machine.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Web framework | Django 5 |
| Database | MySQL; SQLite is available for lightweight local demos |
| Cache | Redis; locmem cache is available for local demo settings |
| Recommendation | Popular ranking, ItemCF, UserCF, lightweight hybrid strategy |
| Evaluation | Precision, recall, K checkpoints, similarity comparison, random split metrics |
| Deployment | Railway, Gunicorn, WhiteNoise |

## Recommended Demo Flow

1. Open the live app: `https://web-production-7e7f.up.railway.app`
2. Log in as `demo_reader` / `DemoPass123!`.
3. Open the profile page and show the seeded ratings and recommendation state.
4. Open the recommendation center and inspect recommended books, scores, and reasons.
5. Open the experiment page and show the offline evaluation metrics.
6. Log out and switch to `thesis_admin` / `AdminPass123!`.
7. Open the dashboard to inspect recent offline jobs and trigger a manual refresh.

Detailed online walkthrough:

[ONLINE_DEMO_GUIDE.md](ONLINE_DEMO_GUIDE.md)

Local manual testing guide:

[MANUAL_TEST_GUIDE.md](MANUAL_TEST_GUIDE.md)

## Local Setup

### 1. Install Dependencies

```powershell
conda run -n bookrec311 python -m pip install -r requirements.txt
```

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Then fill in your local MySQL and Redis values.

### 2. Run Migrations

```powershell
conda run -n bookrec311 python manage.py migrate
```

### 3. Load Data and Build Recommendations

Place `books.csv` and `ratings.csv` under `data/raw/goodbooks/`, then run:

```powershell
conda run -n bookrec311 python manage.py import_goodbooks --source data/raw/goodbooks --limit-ratings 5000
conda run -n bookrec311 python manage.py rebuild_recommendations
conda run -n bookrec311 python manage.py evaluate_recommenders
```

If you do not have the public data files available, seed a compact demo dataset instead:

```powershell
conda run -n bookrec311 python scripts/init_demo_data.py
```

### 4. Start the App

```powershell
conda run -n bookrec311 python manage.py runserver
```

Open:

http://127.0.0.1:8000/

## Local Demo Mode

For a quick click-through demo without Redis, use the MySQL demo settings. This uses Django locmem cache while keeping MySQL as the database:

```powershell
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_mysql_demo
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_mysql_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
conda run -n bookrec311 python manage.py evaluate_recommenders --settings=book_recommender.settings_mysql_demo
Remove-Item Env:DJANGO_SETTINGS_MODULE
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_mysql_demo
```

## Deployment Notes

The Railway web process runs:

```bash
python manage.py collectstatic --noinput
python manage.py evaluate_recommenders --skip-record
gunicorn book_recommender.wsgi:application --bind 0.0.0.0:$PORT
```

The `--skip-record` flag refreshes `artifacts/evaluations/summary.json` on each deployment without duplicating `EvaluationRun` database rows. This keeps the experiment page populated after Railway rebuilds the container.

## Verification

Useful checks before pushing changes:

```powershell
conda run -n bookrec311 python manage.py check
conda run -n bookrec311 pytest tests/test_end_to_end_smoke.py -q
conda run -n bookrec311 pytest tests/test_evaluations.py tests/test_railway_settings.py -q
```

Recent verification snapshots:

- Chinese UI acceptance suite: `61 passed`
- Evaluation artifact deployment tests: `11 passed`
- Railway experiment page: non-empty K checkpoints, precision, recall, and random split metrics verified online

## Project Layout

```text
apps/
  accounts/          Login, registration, profile, and password flows
  catalog/           Home page, catalog list, detail pages, categories
  ratings/           Reader rating flow
  recommendations/   Recommendation generation, caching, and management commands
  evaluations/       Offline metrics and experiment page
  dashboard/         Staff operations dashboard
book_recommender/    Django settings, base templates, static assets
docs/assets/readme/  README screenshots
scripts/             Demo initialization, downloads, validation, scheduled jobs
tests/               Unit tests, smoke tests, deployment configuration tests
```

## Current Status

- Live Railway demo is available.
- The UI is localized for Chinese end users while this README remains English for GitHub visitors.
- Goodbooks-style public interaction data is loaded in the demo environment.
- The experiment page uses real evaluation metrics instead of placeholder data.
- Recommendation explanations appear in the recommendation center and related user-facing flows.