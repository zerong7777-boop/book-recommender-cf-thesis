import json
import os
from pathlib import Path
import subprocess
import sys


def _load_production_settings(env):
    command = (
        "import json;"
        "import book_recommender.settings as s;"
        "print(json.dumps({"
        "'allowed_hosts': s.ALLOWED_HOSTS,"
        "'csrf_trusted_origins': getattr(s, 'CSRF_TRUSTED_ORIGINS', []),"
        "'database': s.DATABASES['default'],"
        "'middleware': s.MIDDLEWARE,"
        "'static_root': str(getattr(s, 'STATIC_ROOT', '')),"
        "'staticfiles_backend': s.STORAGES['staticfiles']['BACKEND'],"
        "}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=os.getcwd(),
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_production_settings_accept_railway_database_variable_names():
    settings = _load_production_settings(
        {
            "DJANGO_SECRET_KEY": "test-secret",
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": ".up.railway.app",
            "CSRF_TRUSTED_ORIGINS": "https://*.up.railway.app",
            "MYSQLDATABASE": "railway",
            "MYSQLUSER": "root",
            "MYSQLPASSWORD": "password",
            "MYSQLHOST": "mysql.railway.internal",
            "MYSQLPORT": "3306",
            "REDIS_URL": "redis://redis.railway.internal:6379/0",
        }
    )

    assert settings["database"]["NAME"] == "railway"
    assert settings["database"]["USER"] == "root"
    assert settings["database"]["PASSWORD"] == "password"
    assert settings["database"]["HOST"] == "mysql.railway.internal"
    assert settings["database"]["PORT"] == "3306"


def test_production_settings_include_railway_host_csrf_and_staticfiles():
    settings = _load_production_settings(
        {
            "DJANGO_SECRET_KEY": "test-secret",
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": ".up.railway.app",
            "RAILWAY_PUBLIC_DOMAIN": "book-demo.up.railway.app",
            "CSRF_TRUSTED_ORIGINS": "https://*.up.railway.app",
            "MYSQL_DATABASE": "book_recommender_cf",
            "MYSQL_USER": "root",
            "MYSQL_PASSWORD": "password",
            "MYSQL_HOST": "127.0.0.1",
            "MYSQL_PORT": "3306",
            "REDIS_URL": "redis://127.0.0.1:6379/1",
        }
    )

    assert ".up.railway.app" in settings["allowed_hosts"]
    assert "book-demo.up.railway.app" in settings["allowed_hosts"]
    assert "https://*.up.railway.app" in settings["csrf_trusted_origins"]
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings["middleware"]
    assert settings["static_root"].endswith("staticfiles")
    assert settings["staticfiles_backend"] == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_procfile_refreshes_evaluation_artifact_before_serving_web():
    procfile = Path("Procfile").read_text(encoding="utf-8")

    assert "python manage.py evaluate_recommenders --skip-record" in procfile
    assert "gunicorn book_recommender.wsgi:application" in procfile
