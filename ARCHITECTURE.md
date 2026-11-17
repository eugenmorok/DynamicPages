# ARCHITECTURE — DynamicPages

Архитектура проекта на основе фактического кода.

## 1. Directory Layout

```
DynamicPages/
├─ manage.py                      # Entry-point CLI
├─ dynamicpages/                  # Root Django project config
│  ├─ __init__.py
│  ├─ settings.py                 # 421 lines. ALL infrastructure config
│  ├─ urls.py                     # Root URL router (admin, ckeditor5, API v1, pages app)
│  ├─ asgi.py                     # ASGI (Channels + WebSocket routing)
│  └─ wsgi.py                    # WSGI standard
├─ pages/                         # Core application (~20 files)
│  ├─ models.py                   # 7 models, 368 lines
│  ├─ managers.py                 # 3 custom managers, 66 lines
│  ├─ views.py                    # Function & class-based views
│  ├─ urls.py                     # 65 URL patterns
│  ├─ api.py                      # REST API (non-DRF, plain JsonResponse), 495 lines
│  ├─ forms.py                    # 5 forms, 101 lines
│  ├─ consumers.py                # 3 WebSocket consumers, 126 lines
│  ├─ tasks.py                    # 4 Celery tasks (Celery app init inline), 174 lines
│  ├─ signals.py                  # post_save / post_delete (cache invalidation)
│  ├─ admin.py                    # PageAdmin, CommentAdmin with bulk actions
│  ├─ rate_limiting.py            # SimpleRateLimiter, RateLimitMiddleware, cors_middleware
│  ├─ monitoring.py               # PerformanceMiddleware, CacheMonitorMiddleware, health_check
│  ├─ sitemaps.py                 # 4 sitemap XML generators (Page, Category, Gallery, Static)
│  ├─ context_processors.py       # common_settings() — shared template data
│  ├─ apps.py                     # PagesConfig.ready() imports signals
│  ├─ tests.py                    # 31 tests in 6 classes
│  └─ migrations/                 # 4 migrations
├─ templates/                     # Jinja2-compatible Django templates
│  ├─ base.html                   # Bootstrap 5 layout (149 lines): navbar, footer, flash messages
│  ├─ home.html                   # Hero section, categories, recent pages, newsletter
│  ├─ pages/
│  │  ├─ detail.html             # Single Page: content, blocks, comments (285 lines)
│  │  ├─ list.html               # Paginated page list + search + category pills
│  │  ├─ form.html               # Page create/edit
│  │  ├─ form_category.html      # Category create/edit
│  │  ├─ confirm_delete.html      # Page delete confirmation
│  │  ├─ gallery.html             # Photo gallery index
│  │  └─ gallery_detail.html      # Single gallery item
│  └─ registration/              # Django auth templates (login, logout, passwords)
├─ Dockerfile / docker-compose.yml
├─ requirements.txt
└─ LICENSE
```

## 2. Settings Layer (`dynamicpages/settings.py`, 421 строки)

Settings module handles **environment variable-driven configuration** via `django-environ`:

### Database
```python
DATABASE_URL = env('DATABASE_URL')  # PostgreSQL connection string
# Falls back silently to:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```
Production requires `psycopg2` or `psycopg`; development auto-selects SQLite.

### Caching
```python
# Production:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': redis_url,
    }
}
# Development fallback:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

### Celery
```python
CELERY_BROKER_URL = redis_url
CELERY_RESULT_BACKEND = redis_url
app.autodiscover_tasks()  # Auto-discover tasks.py in all installed apps
```
Celery app is initialized **inline in `pages/tasks.py`** (standard multi-app pattern).

### Channels
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [redis_url]},
    }
}
ASGI_APPLICATION = 'dynamicpages.asgi.application'
```

### Django-environ env vars (all loaded from .env)

| Variable | Used for |
|---|---|
| `DEBUG` | Debug mode toggle |
| `DATABASE_URL` | PostgreSQL DSN |
| `REDIS_URL` | Cache, broker, channel_layer |
| `SECRET_KEY` | Django secret |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| Various email settings (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`) | SMTP |

### CSP (Content-Security-Policy)
`django-csp` configured with `DIRECTIVES` for `default-src`, `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `frame-src`, `media-src` — including CDNs for Bootstrap and Font Awesome.

### CSRF Trusted Origins
`CSRF_TRUSTED_ORIGINS` set for the Vercel SPA frontend.

## 3. Application Architecture

### Models

7 models in `pages/models.py` (368 lines):

```
Page  ──┬── PageCategory      (FK: Page.category → PageCategory)
        ├── PageBlock         (FK: PageBlock.page → Page)
        └── Comment           (FK: Comment.page → Page)
        
Comment ── Comment (parent FK for replies)
        
MediaGallery ── PageCategory
Subscription  (standalone)
SiteSetting   (standalone, key-value store)
```

**Auto-slug generation**: `Page.save()` calls `slugify(self.title)` + `django.utils.text.slugify` when slug is blank. `PageCategory.save()` similarly.

**Atomic view_count**: `Page.increment_view_count()` uses `F('view_count') + 1` with `update_fields=['view_count']` to avoid race conditions.

### Managers (pages/managers.py)

Three custom managers:

#### `PublishedPageManager`
- Filters: `status='published' AND published_at__lte=now()`
- Eager loading: `select_related(category, author) + prefetch_related(blocks)`
- Special method `with_category_deferred()`: `.defer('default')` (heavy CKEditor5 field excluded from list views)

#### `ActiveCommentManager`
- Filters: `status='approved' AND is_spam=False`
- Eager loading: `select_related(author, page)`
- Alias: `approved_objects = self` (self-referential `__init__` for reverse compatibility)

#### `ActiveMediaGalleryManager`
- Filter: `is_active=True`
- Loading: `select_related(category)`
- Ordering: `-created_at`

### Views (`pages/views.py`)

**Function-based views:**
- `home()` — featured pages from cache, categories, newsletter
- `page_detail()` — single page + related pages (cache: 2 min) + comments (cache: 2 min) + increment_view_count
- `category_detail()` — category pages + cached (15 min)
- `gallery_list()`, `gallery_detail()` — MediaGallery CRUD
- `subscribe()`, `unsubscribe()` — Subscription handling
- `add_comment()`, `add_reply()` — Comment submission with honeypot field validation
- `sitemap_xml()`, `robots_txt()` — static sitemap/robots

**Class-based views:**
- `PageListView` — paginated (12 per page), `published_objects`, with search + category filter
- `PageCreateView`, `PageUpdateView`, `PageDeleteView` — login_required, PageForm

**Search pattern** (fixed): `Q(default__icontains=q)` — **not** `content__icontains` (field was renamed in migration 0003).

**Template data helpers:**
- `comments_to_dict()` — builds nested dict: `{pk: {comment, replies: [...]}}` keyed by page slug
- `_build_comment_context()` — shared comment rendering context (name, reply_count, comment_list)
- `count_comments()` — counts approved comments for a page

### Forms (`pages/forms.py`, 101 lines)

| Form | Model | Extra Fields | Notes |
|---|---|---|---|
| `PageForm` | Page | `content` (CKEditor5Widget), `excerpt`, `meta_keywords` | Widget overrides; slug is readonly after save |
| `PageCategoryForm` | PageCategory | — | |
| `PageBlockForm` | PageBlock | `content` (CKEditor5Widget) | Meta.fields = `['default']` (not `'content'`) |
| `SiteSettingForm` | SiteSetting | `value` | |
| `SearchForm` | — | `q`, `category` | Manual Form (not ModelForm) |
| `CommentForm` | — | (pages/comments.py) | Honeypot field for spam protection |
| `ReplyForm` | — | (pages/comments.py) | Honeypot field |

### URLs (`pages/urls.py`, 65 lines) — Full routing

```
[public] /                    → home
[public] /pages/              → PageListView
[public] /page/<slug>/        → page_detail
[public] /category/<slug>/    → category_detail
[public] /subscribe/          → subscribe
[public] /unsubscribe/<pk>/   → unsubscribe
[public] /gallery/            → gallery_list
[public] /gallery/<pk>/       → gallery_detail
[public] /sitemap.xml         → sitemap_xml
[public] /robots.txt          → robots_txt
[auth]   /create/             → PageCreateView
[auth]   /pages/<slug>/edit/  → PageUpdateView
[auth]   /pages/<slug>/delete/→ PageDeleteView
[auth]   /blocks/create/<slug>/→ page_block_create
[auth]   /blocks/<pk>/delete/ → page_block_delete
[auth]   /categories/create/  → CategoryCreateView
[auth]   /categories/<slug>/edit/ → CategoryUpdateView
[auth]   /categories/<slug>/delete/ → CategoryDeleteView
[comment] /page/<slug>/comment/   → add_comment
[comment] /page/<slug>/comment/<pk>/reply/ → add_reply
```

**Root router** (`dynamicpages/urls.py`, 63 lines):
```
/admin/           → django.contrib.admin
/accounts/        → Django auth URLs (login/logout/password reset)
/ckeditor5/       → django_ckeditor_5
api/health/       → api.api_health
api/              → api.api_index
api/v1/           → includes all api_patterns
sitemap/          → views.sitemap_xml
robots.txt        → views.robots_txt
/                 → includes pages.urls
```

API v1 patterns:
```
pages/            → api_pages_list
pages/<pk>/       → api_pages_detail
categories/       → api_categories
gallery/          → api_gallery_list
gallery/<pk>/     → api_gallery_detail
pages/<page_id>/comments/    → api_comments  (GET) / api_submit_comment (POST)
pages/<page_id>/comments/submit/ → api_submit_comment
admin/stats/      → api_admin_stats
```

### REST API (`pages/api.py`, 495 lines) — no DRF

Standard `JsonResponse` based API with these patterns:

**Response envelope (`_json_response`)**:
```python
{"success": True/False, "data": ..., "error": {...}}  # on failure
```

**Pagination (`_paginate`)**:
```python
{
    "page": 1, "per_page": 20, "total": 100, "total_pages": 5,
    "next_page": 2, "prev_page": None
}
```
Parameters: `page` (default 1), `per_page` (default 20, max 50).

**CORS (`_add_cors`)**:
- Origin: `https://dynamicpages-frontend.vercel.app` (production) or `*` (development)
- Applied via view decorator with dedup tracking (`_CORS_APPLIED` set)
- Headers: `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods`

**Key API endpoints:**
| Endpoint | Caching | Auth |
|---|---|---|
| `api_index()` | none | none |
| `api_health()` | none | none |
| `api_pages_detail(pk)` | 2 min cache | none |
| `api_pages()` | @cache_page(60) | none |
| `api_categories()` | @cache_page(60) | none |
| `api_comments(page_id)` | 2 min cache | none |
| `api_submit_comment(page_id)` | none | Honeypot required |
| `api_gallery()` | @cache_page(120) | none |
| `api_gallery_detail(pk)` | none | none |
| `api_admin_stats()` | none | login_required |

### Caching Architecture

| Resource | Cache Key | TTL | Method |
|---|---|---|---|
| Home page | `home_featured` | 300s | `cache.get/set` |
| Featured pages | `featured_pages` | 300s | `cache.get/set` |
| Page detail | `page_detail:{slug}` | 120s | `cache.get/set` |
| Related pages | `related:{slug}` | 120s | `cache.get/set` |
| Category list | `category:{slug}` | 900s | `cache.get/set` |
| Comments | `comments:{slug}` | 120s | `cache.get/set` |
| API pages | `api_pages_page:{page}` | 60s | `cache.get/set` |
| API categories | `api_categories_list` | 60s | `cache.get/set` |
| API gallery | `api_gallery_page:{page}` | 120s | `cache.get/set` |

**Signal-based invalidation (`signals.py`)**:
```python
@receiver(post_save, sender=Page)
def page_saved(sender, instance, **kwargs):
    cache.delete(f'page_detail:{slug}')
    cache.delete(f'related:{slug}')
    cache.delete(f'comments:{slug}')
    cache.delete('featured_pages')

@receiver(post_delete, sender=Page)
def page_deleted(sender, instance, **kwargs):
    cache.delete('page_list_published')
    cache.delete('featured_pages')
```
**Note**: Only targeted keys are deleted — **not** `cache.clear()` (this was a critical fix in Stage 5b).

### Context Processor (`context_processors.py`)
```python
def common_settings(request):
    return {
        'site_title': ...,
        'site_description': ...,
        'categories': active_categories,
        'categories_with_page_count': categories with page_count annotation,
        'last_year': current year,
    }
```
All templates that extend `base.html` get these variables automatically.

### Template Structure

**base.html** (149 lines):
- Loads static (CSS from `static/css/style.css`)
- Dynamic navbar: Home, Pages, active categories (from `categories` context var), Gallery
- Auth-aware: login/register buttons vs. username/logout
- Flash messages via Django messages framework
- Bootstrap 5 JS + Font Awesome SVG icons
- Footer with site info, navigation links, contact info

**home.html**:
- Hero section with CTA buttons
- Newsletter subscription form
- Category pills with `card` hover effects
- Recent published pages (card grid)

**detail.html** (285 lines):
- Breadcrumbs: Home → Category → Page title
- Meta info strip: category, date, views, author
- Featured image (if present)
- Content: `{{ page.default|safe }}` (CKEditor5 rendered)
- Blocks: `{{ block.default|safe }}` with optional image
- Edit/delete links for authenticated users
- Related pages: cached, limited to 3
- Comments: threaded (replies), honeypot spam protection, `{{ comment.text }}`, reply count
- Comment submission: requires honeypot field (hidden) to be empty

**list.html** (141 lines):
- Search form with category filter
- Category pills for filtering
- Card grid (3-col responsive)
- Pagination with URL param preservation

### Sitemaps (`sitemaps.py`, 80 lines)

4 sitemap classes, each using `.iterator(chunk_size=...)` for memory efficiency:

| Sitemap | URL patterns | Query |
|---|---|---|
| `StaticSitemap` | `/sitemap.xml` | Static URL list |
| `PageSitemap` | `/page/<slug>/` | `Page.published_objects` |
| `CategorySitemap` | `/category/<slug>/` | `PageCategory.objects.all()` |
| `GallerySitemap` | `/gallery/<pk>/` | `MediaGallery.active_objects` |

Generated via `sitemap_xml()` view as XML response. Also available via Django's built-in siteframework at `/sitemap/`.

### Rate Limiting (`rate_limiting.py`)

```python
class SimpleRateLimiter:
    # Per client (IP + hash of path)
    # Cache keys: 'rl:{md5_hash}'
    # Window: 60 seconds
    # Uses cache.incr() for atomic counter
    
class RateLimitMiddleware:
    # Skips for authenticated users & /admin/
    # Path-specific rates in RATE_LIMITS dict:
    #   /api/v1/       → 120 req/min, burst 30
    #   /api/v1/pages/ → 60 req/min, burst 20
    #   /api/v1/gallery/ → 90 req/min, burst 25
    # Adds X-RateLimit-* response headers
    # Returns 429 JSON on limit exceeded
```

### Performance Monitoring (`monitoring.py`, 179 lines)

```python
class PerformanceMiddleware:
    # Measures response time, logs slow requests
    # Adds X-Response-Time header
    
class CacheMonitorMiddleware:
    # Tracks cache hits/misses per request
    # Adds Cache-Miss-COUNT header

def health_check() → dict:
    # DB, Cache, Celery (ping broker), Channels (ping channel_layer)
    return {'database': 'ok'/'error', 'cache': 'ok'/'error', 'celery': 'ok'/'error', 'channels': 'ok'/'error'}

def get_system_metrics() → dict:
    # Memory, CPU (via psutil), request counts, uptime
```

### WebSocket (`consumers.py`, 126 lines)

3 consumers via Django Channels:

| Consumer | Purpose |
|---|---|
| `CommentWebSocketConsumer` | Real-time comment notifications (new/reply) |
| `PageActivityConsumer` | Page activity events |
| `AdminNotificationConsumer` | Admin panel notifications |

### ASGI configuration

ASGI routing uses `pages.websocket_urlpatterns` to map WebSocket URL paths to consumers.

## 4. Request Flow Examples

### 1. Request to `/page/my-page/`

```
Client
  → HTTP GET /page/my-page/
  → dynamicpages/urls.py: includes pages.urls
  → pages/urls.py: page_detail(slug)
  → pages/views.py:
    1. Page.published_objects.get(slug=slug)  ← prefetch_related(blocks), select_related(category, author)
    2. Page.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    3. Cache: page_detail:{slug}, related:{slug}, comments:{slug}
    4. Related pages (max 3, same category, != current)
    5. Approved comments via active_objects
    6. count_comments() for page
    7. Template: pages/detail.html → renders base.html + content
  → Response: HTML 200
```

### 2. API Request to `/api/v1/pages/`

```
Client
  → HTTP GET /api/v1/pages/
  → dynamicpages/urls.py: api_patterns
  → pages/api.py: api_pages()
  → RateLimitMiddleware checks client IP
  → cache.get('api_pages_page:1') → return cached or:
     1. Page.published_objects.with_category_deferred()
    2. paginate(result, page, per_page)
    3. _json_response with data list + pagination meta
    4. _add_cors decorator applies Access-Control headers
  → Response: JSON 200
```

## 5. Database Schema (4 migrations)

See `MIGRATIONS.md` for full migration history.

### Final schema summary

| Model | Table | Key fields | Indexes (from models) | Indexes (from migrations) |
|---|---|---|---|---|
| Page | pages_page | id, title, slug, status, published_at, is_featured, view_count, category_id, author_id | — | (title, slug), (status, published_at), (category, status), (is_featured, published_at), (status, published_at, title, slug, category_id) |
| PageCategory | pages_pagecategory | id, title, slug, is_active | (title) | — |
| PageBlock | pages_pageblock | id, page_id, title, default, image, ordering | — | — |
| Comment | pages_comment | id, page_id, parent_id, status, is_spam, name, text | — | (page, status), (page, -created_at), (status, -created_at), (page, status, created_at, text, name, author_id) |
| Subscription | pages_subscription | id, email, active | — | (email, active) |
| MediaGallery | pages_mediagallery | id, category_id, image, thumbnail, is_active, created_at | — | (is_active, -created_at), (category, is_active, created_at) |
| SiteSetting | pages_sitesetting | id, key, value, label | — | — |

## 6. Email Infrastructure

| Email | When sent | To |
|---|---|---|
| Comment notification | `send_email_notification` Celery task | site_email (from SiteSetting) |
| Subscription digest | `send_subscription_digest` Celery beat periodic | Each active Subscriber |
| Password reset | Django built-in | User |
| Unsubscribe confirmation | `unsubscribe` view | Subscriber |

SMTP config via Django email backend (configured in settings.py).

## 7. Deployment

### Docker (docker-compose.yml)

Multi-service compose:
- `web`: Django app (builds from Dockerfile)
- `postgres`: PostgreSQL
- `redis`: Redis (cache + broker + channel_layer)
- `celery_worker`: Celery worker
- `celery_beat`: Celery beat (periodic tasks)

### Direct (no Docker)

1. Set `.env` with DATABASE_URL, REDIS_URL, SECRET_KEY
2. `python manage.py migrate`
3. `python manage.py runserver` or `gunicorn dynamicpages.wsgi:application`
4. `celery -A dynamicpages worker -l info`
5. `celery -A dynamicpages beat -l info`
