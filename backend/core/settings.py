"""
Django settings for REPORTIX Retail POS.

Конвенции согласованы с другими продуктами бренда REPORTIX:
django-environ для конфигурации, django-rq для фоновых задач, django-redis
для кэша, DRF с сессионной аутентификацией, TZ Asia/Tashkent.
"""

import os
import sys
from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, False),
)

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

DEBUG = env("DEBUG")

# SECRET_KEY обязателен в production; небезопасный дефолт — только для DEBUG.
from core.env_utils import get_secret_key  # noqa: E402

SECRET_KEY = get_secret_key(env("SECRET_KEY", default=""), DEBUG)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend"])

# Распознаём как Django-тесты (manage.py test), так и pytest —
# чтобы в тестах использовать locmem-кэш и не обращаться к Redis.
_TESTING = (
    "test" in sys.argv
    or any(a.startswith("test") for a in sys.argv)
    or "pytest" in sys.modules
    or bool(os.environ.get("PYTEST_VERSION"))
)

# --- Applications ----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_rq",
    "apps.common",
    "apps.tenants",
    "apps.catalog",
    "apps.inventory",
    "apps.sales",
    "apps.voice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Resolves request.tenant from the authenticated user's membership.
    "apps.common.middleware.TenantContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# --- Database --------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3"),
}

AUTH_USER_MODEL = "tenants.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / TZ -------------------------------------------------------------
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --- Static / Media --------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache (Redis) ---------------------------------------------------------
if _TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "reportix-test-cache",
        }
    }
else:
    REDIS_URL = env("REDIS_URL", default="redis://redis:6379/1")
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "reportix",
            "TIMEOUT": 300,
        }
    }

# --- DRF -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Троттлинг только для чувствительных точек через ScopedRateThrottle
    # (глобальный троттлинг не включаем, чтобы не влиять на остальной API).
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
    },
}

# Максимальный размер загружаемого голосового аудио (10 МБ) → 413.
VOICE_MAX_AUDIO_BYTES = env.int("VOICE_MAX_AUDIO_BYTES", default=10 * 1024 * 1024)

# --- Security --------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

_csrf_origins = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = _csrf_origins
elif DEBUG:
    CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    CSRF_TRUSTED_ORIGINS = []

_cors_origins = env.list("CORS_ALLOWED_ORIGINS", default=[])
if _cors_origins:
    CORS_ALLOWED_ORIGINS = _cors_origins
elif DEBUG:
    CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)

# --- Voice / STT -----------------------------------------------------------
# Провайдер распознавания речи: "mock" (по умолчанию, без ключей) | "google".
STT_PROVIDER = env("STT_PROVIDER", default="mock")
GOOGLE_STT_MODEL = env("GOOGLE_STT_MODEL", default="default")

# --- Background jobs (django-rq) -------------------------------------------
RQ_REDIS_URL = env("RQ_REDIS_URL", default=env("REDIS_URL", default="redis://redis:6379/1"))
RQ_QUEUES = {
    "default": {
        "URL": RQ_REDIS_URL,
        "DEFAULT_TIMEOUT": 300,
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "console"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
