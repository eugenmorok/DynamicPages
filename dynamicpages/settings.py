"""
Django settings for dynamicpages project.
Настроен PostgreSQL для production, SQLite для development.
Включены CSP, WhiteNoise, security middleware.
"""
import os
from pathlib import Path
from environ import Env

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment setup
env = Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-change-this-in-production!'),
    DATABASE_URL=(str, ''),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', 'testserver']),
)
Env.read_env(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # CKEditor 5
    'ckeditor5',
    'django_ckeditor_5',
    'csp',  # Content Security Policy
    # Custom apps
    'pages',
]

# Middleware: CSP, Security
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',  # Last middleware (before response sent)
]

# Rate limiting for API endpoints
RATE_LIMIT_MIDDLEWARE_ENABLED = True

ROOT_URLCONF = 'dynamicpages.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'pages.context_processors.common_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'dynamicpages.wsgi.application'

# Database configuration
db_url = env('DATABASE_URL')
if db_url:
    DATABASES = {'default': env.db('DATABASE_URL')}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True

# Application version & startup
VERSION = '1.0.0'
import time as _time
STARTUP_TIME = _time.time()

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_URL = os.environ.get('SITE_URL', 'https://example.com')

# ============================================================
# Performance: Cache configuration
# ============================================================
# Production: Redis/Memcached, Development: locmem
CACHE_URL = os.environ.get('CACHE_URL', 'locmemcache://')
if CACHE_URL.startswith('redis'):
    import redis
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': CACHE_URL,
            'KEY_PREFIX': 'dynamicpages',
            'OPTIONS': {
                'MAX_ENTRIES': 10000,
                'CULL_FACTOR': 0,  # Don't cull, just evict LRU
            },
            'TIMEOUT': 600,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'dynamicpages-cache',
            'KEY_PREFIX': 'dynamicpages',
            'TIMEOUT': 600,
        }
    }
    # Redis auto-detection for dev (performance parity with production)
    _redis_found = False
    try:
        import redis
        _redis_found = True
        redis_url = os.getenv(
            'REDIS_URL',
            'redis://127.0.0.1:6379/1',
        )
        client = redis.Redis.from_url(redis_url)
        if client.ping():  # Verify connection
            CACHES['default'] = {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'KEY_PREFIX': 'dynamicpages',
                'TIMEOUT': 600,
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                },
            }
            client.close()
    except ImportError:
        pass  # django-redis / redis libraries not installed
    except Exception:
        pass  # Connection refused or other error — keep locmem cache
    finally:
        del _redis_found

# ============================================================
# Performance: Query optimization
# ============================================================
# Enable connection pooling for PostgreSQL in production
if db_url and db_url.startswith('postgresql'):
    DATABASES['default']['CONN_MAX_AGE'] = 600
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    DATABASES['default']['OPTIONS'] = {
        'init_command': 'SET sql_mode=\'STRICT_TRANS_TABLES\'',
        'connect_timeout': 10,
    }

# ============================================================
# Performance: Compression and static
# ============================================================
# WhiteNoise 6.x doesn't have CompressMediaMiddleware — use CompressedManifestStaticFilesStorage instead
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# ============================================================
# Production security (only applied when DEBUG=False)
# ============================================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = False
    SESSION_COOKIE_AGE = 86400  # 24 hours (more stable session)
    SESSION_SAVE_EVERY_REQUEST = False  # Better performance

# ============================================================
# CSP (Content Security Policy) configuration
# ============================================================
# django-csp <4.0 format: CSP_<DIRECTIVE> = (...)
# For compatibility with all django-csp versions:

CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'",
                        "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"),
        'style-src': ("'self'", "'unsafe-inline'",
                       "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com",
                       "https://fonts.googleapis.com"),
        'img-src': ("'self'", "data:", "https:", "http:"),
        'font-src': ("'self'",
                      "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"),
        'connect-src': ("'self'", "https://cdn.jsdelivr.net"),
        'media-src': ("'self'", "blob:"),
        'worker-src': ("'self'", "blob:"),
        'frame-src': ("'none'"),
        'object-src': ("'none'"),
        'base-uri': ("'self'",),
        'form-action': ("'self'",),
        'upgrade-insecure-requests': None,
    },
}
CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']

# ============================================================
# Logging configuration
# ============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'security': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'pages': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ============================================================
# CKEditor 5 configuration
# ============================================================
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading', '|', 'bold', 'italic', 'link',
            'bulletedList', 'numberedList', '|',
            'blockQuote', 'insertImage', 'mediaEmbed', '|',
            'removeFormat', 'sourceEditing'
        ],
    },
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading2', 'heading3', '|',
            'bulletedList', 'numberedList', '|',
            'blockQuote',
        ],
        'toolbar': [
            'heading', '|', 'bold', 'italic', 'link',
            'bulletedList', 'numberedList', 'codeBlock', '|',
            'blockQuote', 'insertImage', 'mediaEmbed', '|',
            'undo', 'redo', '|',
            'removeFormat', 'sourceEditing'
        ],
    },
}
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = True
CKEDITOR_5_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CKEDITOR_5_UPLOAD_FILE_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'pdf', 'doc', 'docx']
CKEDITOR_5_FILE_UPLOAD_PERMISSION = 'authenticated'
CKEDITOR_5_UPLOAD_DIR = 'uploads/ckeditor'
CK_EDITOR_5_UPLOAD_FILE_VIEW_NAME = 'ck_editor_5_upload_file'

# Maximum upload size for CKEditor
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Messages
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'webmaster@localhost'

# Custom error handlers
handler404 = 'pages.views.page_not_found'
handler500 = 'pages.views.server_error'

# ============================================================
# Celery — asynchronous task queue (optional, needs celery installed)
# ============================================================
try:
    from celery.schedules import crontab
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

# Celery defaults (override via env or when celery is installed)
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Bangkok'

CELERY_BEAT_SCHEDULE = {}
if HAS_CELERY:
    CELERY_BEAT_SCHEDULE = {
        'send_weekly_digest': {
            'task': 'pages.tasks.send_subscription_digest',
            'schedule': crontab(day_of_week=1, hour=10, minute=0),
        },
        'cleanup_old_subscriptions': {
            'task': 'pages.tasks.cleanup_old_subscriptions',
            'schedule': crontab(day_of_week=0, hour=2, minute=0),
        },
    }

# ============================================================
# Celery advanced settings
# ============================================================
CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '4'))
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get('CELERY_MAX_TASKS_PER_CHILD', '1000'))
CELERY_TASK_ACKNOWLEDGES_LATE = True
CELERY_TASK_REDELIVER_ON_WORKER_LOST = True
CELERY_BROKER_TRANSPORT_OPTIONS = {'max_retries': 3, 'interval_start': 0, 'interval_step': 0.2}

# ============================================================
# Channels — WebSocket channel layer (Redis backend)
# ============================================================
ASGI_CHANNELS_ENABLED = True
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379/1')],
            'capacity': 1500,  # max queue per channel
            'expiry_length': 10,  # seconds messages stay in queue
        },
    },
}

# ============================================================
# CSRF & CORS
# ============================================================
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS', list, [])
