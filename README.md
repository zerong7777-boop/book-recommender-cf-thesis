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

This repository ships a Goodbooks-style import command. Place `books.csv` and `ratings.csv` under `data/raw/goodbooks/`, then run:

```powershell
conda run -n bookrec311 python manage.py import_goodbooks --source data/raw/goodbooks --limit-ratings 5000
conda run -n bookrec311 python manage.py rebuild_recommendations
conda run -n bookrec311 python manage.py evaluate_recommenders
```

For a full import, omit `--limit-ratings`. Dataset users are stored as `ImportedInteraction`; they are not login accounts. For a self-contained smoke/demo setup without public data files, the demo initializer below seeds a compact sample catalog automatically.

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

## Daily scheduled rebuild

For the formal Windows local demo, register a daily Task Scheduler job:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_daily_rebuild_task.ps1 -SettingsModule book_recommender.settings -DailyAt 02:00
```

For the MySQL demo fallback without Redis:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_daily_rebuild_task.ps1 -SettingsModule book_recommender.settings_mysql_demo -DailyAt 02:00
```

The scheduled task runs the same Django management command used by the dashboard manual trigger.

## Redis-backed read verification

The formal spec path uses `book_recommender.settings`, which reads Redis from `REDIS_URL`. Start Redis, then run:

```powershell
conda run -n bookrec311 python scripts/verify_redis_cache_path.py
```

Expected output:

```text
redis_cache_path_ok hot_result_id=1 processed_users=1
```

The `book_recommender.settings_mysql_demo` setting uses locmem cache only for local click-through demos and does not prove the Redis-backed read path.

Latest local formal-path status:

```text
redis_unverified: no Redis server was listening at redis://127.0.0.1:6379/1 during the latest local check.
```

Start Redis first, then rerun `scripts/verify_redis_cache_path.py` to turn this into a positive `redis_cache_path_ok ...` proof.

## Evaluation

Generate the thesis evaluation artifact summary:

```powershell
conda run -n bookrec311 python manage.py evaluate_recommenders
```

## Start the app

```powershell
conda run -n bookrec311 python manage.py runserver
```

## Quick local demo mode

If you only want to click through the app locally without preparing `.env`, MySQL credentials, and Redis first, use the SQLite + locmem demo mode:

```powershell
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_local_demo
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_local_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
Remove-Item Env:DJANGO_SETTINGS_MODULE
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_local_demo
```

Detailed click-by-click manual test instructions live in [MANUAL_TEST_GUIDE.md](E:/projects/book-recommender-cf/MANUAL_TEST_GUIDE.md).

## UI base

The current thesis demo UI keeps the existing Django backend and adapts two mature open-source layout directions for the visible product layer:

1. A `Booksaw`-inspired bookstore storefront for homepage, catalog, recommendations, and account pages
2. A `Tabler`-style operations layout for the staff dashboard

This refresh is intentionally template-first. The collaborative-filtering pipeline, account flow, and dashboard actions still use the original Django views and services.

## Spec alignment status

The local MySQL demo has imported a bounded Goodbooks-10k slice (`ImportedInteraction.objects.count() == 5000`) and generated `hot`, `ItemCF`, `UserCF`, and lightweight hybrid recommendation outputs. The code supports Redis-backed reads under the formal settings, while `book_recommender.settings_mysql_demo` remains available as a click-through fallback for machines without Redis.

The downloaded Goodbooks CSV files are local inputs under `data/raw/goodbooks/` and are intentionally ignored by Git. The latest local Redis proof is still pending because no Redis service was available on `127.0.0.1:6379`.

## 演示流程

1. 在浏览器里打开站点首页。
2. 用演示读者账号 `demo_reader` / `DemoPass123!` 登录，或者直接说“使用 demo_reader 演示账号登录”。
3. 打开个人中心，查看已写入的评分和推荐状态。
4. 打开推荐中心，查看当前推荐结果和推荐理由。
5. 退出后切换到 `thesis_admin` / `AdminPass123!`。
6. 打开管理页，查看最近的离线任务并手动触发重建。

## Verification

Before wrapping up a local change, run:

```powershell
conda run -n bookrec311 python manage.py check
conda run -n bookrec311 pytest tests/test_end_to_end_smoke.py -q
```
