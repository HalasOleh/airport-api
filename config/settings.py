from decouple import config
from pathlib import Path
import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True") == "True"

# Not a wildcard any more: AllowedHostsOriginValidator reads this list to
# decide which sites may open a WebSocket, and it returns True for every
# origin as soon as "*" appears here. With the JWT now living in a cookie,
# that would leave the socket open to cross-site hijacking.
ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
).split(",") if h.strip()]


# Application definition

INSTALLED_APPS = [
    'daphne',
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Required by pgvector's HnswIndex, which subclasses PostgresIndex.
    'django.contrib.postgres',
    'airports',
    'user',
    'rest_framework',
    'drf_spectacular',
    'tickets',
    'django_filters',
    'ai_bot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Kyiv'

USE_I18N = True

USE_TZ = True

DATE_FORMAT = "d/m/Y"

DATETIME_FORMAT = "d/m/Y"

STATIC_URL = 'static/'

REST_FRAMEWORK = {
        "DEFAULT_FILTER_BACKENDS": [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
        ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_PERMISSION_CLASSES": [
        "config.permissions.IsAdminAllORIsAuthenticatedReadOnly",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "user.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "checkout": "10/minute",
    }
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --- Cookie-based JWT -------------------------------------------------
#
# The WebSocket API (`new WebSocket(url)`) has no way to set request
# headers, so an Authorization header can never reach the WS handshake from
# a browser. A cookie can: the browser attaches it to every request to the
# origin, handshake included. These names are shared by the three places
# that read the token - the login view, CookieJWTAuthentication (HTTP) and
# JWTAuthMiddleware (WebSocket) - so they cannot drift apart.
JWT_ACCESS_COOKIE = "access_token"
JWT_REFRESH_COOKIE = "refresh_token"

# httponly: JavaScript cannot read it, so an XSS cannot exfiltrate the token.
# secure: HTTPS only. Off under DEBUG because localhost is plain http.
# samesite="Lax": the cookie is not sent on cross-site POSTs, which removes
# the most common CSRF vector - but not all of them, so CSRF checks stay on.
JWT_COOKIE_SECURE = not DEBUG
JWT_COOKIE_SAMESITE = "Lax"
# Path "/" so one cookie covers both /api/... and /ws/... on this origin.
JWT_COOKIE_PATH = "/"

AUTH_USER_MODEL = "user.User"

SPECTACULAR_SETTINGS = {
    'TITLE': 'Airports API',
    'DESCRIPTION': 'By tickets',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

#SMTP Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'#smtp
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

BASE_URL = os.getenv("BASE_URL")

ASGI_APPLICATION = "config.asgi.application"

# Redis is shared by the Channels layer and the chat context cache.
# In Docker, "redis" is the service name from docker-compose.yml.
# On Render, REDIS_URL will contain the address of the managed Redis instance.
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379/0",
)

CHAT_CONTEXT_CACHE_TIMEOUT = int(
    os.getenv("CHAT_CONTEXT_CACHE_TIMEOUT", 60 * 60)
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "airport-default",
    },
    "chat_context": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "airport-chat",
        "TIMEOUT": CHAT_CONTEXT_CACHE_TIMEOUT,
    },
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}