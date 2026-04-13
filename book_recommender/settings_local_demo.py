import os
from pathlib import Path

from .settings import *  # noqa: F401,F403


DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

LOCAL_DEMO_DB_DIR = Path(
    os.environ.get("BOOKREC_LOCAL_DEMO_DIR", "E:/codex-home/tmp/book-recommender-cf-demo")
)
LOCAL_DEMO_DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(LOCAL_DEMO_DB_DIR / "local-demo-v2.sqlite3"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "book-recommender-local-demo-cache",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
