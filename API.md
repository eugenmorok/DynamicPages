# API Reference — DynamicPages REST API

Без DRF — чистый Django `JsonResponse`. Все ответы обернуты.

## Response Envelope

Успешный ответ:
```json
{
  "success": true,
  "data": { ... }
}
```

Ошибка:
```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "detail": "Human-readable message"
  },
  "data": { ... }
}
```

## Pagination Meta

```json
{
  "page": 1,
  "per_page": 20,
  "total": 150,
  "total_pages": 8,
  "next_page": 2,
  "prev_page": null
}
```

Параметры запроса: `page` (по умолчанию 1), `per_page` (по умолчанию 20, макс. 50).

## Rate Limiting

Middleware (`RateLimitMiddleware`) применяет лимиты к **неавторизованным** клиентам:

| Path prefix | Rate limit | Burst |
|---|---|---|
| `/api/v1/` | 120 req/min | 30 |
| `/api/v1/pages/` | 60 req/min | 20 |
| `/api/v1/gallery/` | 90 req/min | 25 |

Заголовки ответа: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.

**При превышении:** HTTP 429 `{"error": "Rate limit exceeded", "detail": "Too many requests"}`.

Аутентифицированные пользователи и `/admin/` — пропускаются.

## CORS

Декоратор `_add_cors` добавляет:
```
Access-Control-Allow-Origin: https://dynamicpages-frontend.vercel.app  (production)
                          или *  (development)
Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

## Health Check

```
GET /api/health/
```

**Response:**
```json
{
  "success": true,
  "data": {
    "database": "ok" | "error",
    "cache": "ok" | "error",
    "celery": "ok" | "error",
    "channels": "ok" | "error",
    "timestamp": "2026-11-17T..."
  }
}
```

Проверяет доступность PostgreSQL/SQLite, Redis, Celery broker, Channels channel_layer.

## API Index

```
GET /api/
```

**Response:**
```json
{
  "success": true,
  "data": {
    "version": "v1",
    "endpoints": {
      "pages_list": "/api/v1/pages/",
      "pages_detail": "/api/v1/pages/{id}/",
      "categories": "/api/v1/categories/",
      "gallery": "/api/v1/gallery/",
      "gallery_detail": "/api/v1/gallery/{id}/",
      "comments": "/api/v1/pages/{page_id}/comments/",
      "submit_comment": "/api/v1/pages/{page_id}/comments/submit/",
      "admin_stats": "/api/v1/admin/stats/"
    }
  }
}
```

## Pages API

### List Pages

```
GET /api/v1/pages/?page=1&per_page=20&search=keyword&category=tech
```

Параметры:
| Параметр | Описание |
|---|---|
| `page` | Номер страницы (default 1) |
| `per_page` | Количество (default 20, max 50) |
| `search` | Поиск по `title` + `excerpt` |
| `category` | Фильтр по slug категории |

**Response body — `data`:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "My Page",
      "slug": "my-page",
      "excerpt": "Brief description...",
      "category": { "id": 1, "title": "Tech", "slug": "tech" },
      "author": { "id": 1, "username": "admin" },
      "status": "published",
      "published_at": "2026-11-17T10:00:00Z",
      "is_featured": false,
      "view_count": 42,
      "blocks": [],
      "featured_image": "https://example.com/media/pages/2026/11/image.png",
      "comment_count": 5
    }
  ],
  "pagination": { ... }
}
```

При `category` фильтрации используется `PublishedPageManager.with_category_deferred()`.

Detail response uses `published_objects.get(slug=slug)` with full objects.

### Page Detail

```
GET /api/v1/pages/{id}/
```

**Response body — `data`:**
```json
{
  "id": 1,
  "title": "My Page",
  "slug": "my-page",
  "excerpt": "Brief description...",
  "default": "<p>Full CKEditor5 content...</p>",
  "meta_title": "SEO Title",
  "meta_description": "SEO description...",
  "meta_keywords": "tech, programming",
  "category": { "id": 1, "title": "Tech", "slug": "tech" },
  "author": { "id": 1, "username": "admin" },
  "status": "published",
  "published_at": "2026-11-17T10:00:00Z",
  "is_featured": true,
  "view_count": 42,
  "featured_image": "https://example.com/media/pages/2026/11/image.png",
  "blocks": [
    {
      "id": 1,
      "title": "Block Title",
      "default": "<p>Block content...</p>",
      "image": "https://example.com/media/blocks/2026/11/block.png",
      "ordering": 1
    }
  ],
  "comment_count": 5,
  "related_pages": [
    {
      "id": 5,
      "title": "Related Page 1",
      "slug": "related-page-1",
      "excerpt": "..."
    }
  ]
}
```

**Кэширование:** 2 минуты по ключу `page_detail:{slug}`.

**view_count:** атомарный инкремент через `F('view_count') + 1` (отдельный UPDATE, **не** дублирующий).

## Categories API

### List Categories

```
GET /api/v1/categories/
```

**Response body — `data`:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Tech",
      "slug": "tech",
      "description": "Technology articles",
      "is_active": true,
      "page_count": 15,
      "created_at": "2026-11-15T..."
    }
  ]
}
```

**Кэширование:** 60 секунд.

## Gallery API

### List Gallery

```
GET /api/v1/gallery/?page=1&per_page=20&category=tech
```

**Response body — `data`:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Photo Title",
      "description": "Photo description",
      "image": "https://example.com/media/gallery/2026/11/photo.jpg",
      "thumbnail": "https://example.com/media/gallery/thumb_/photo.jpg",
      "category": {
        "id": 1,
        "title": "Tech",
        "slug": "tech"
      },
      "is_active": true,
      "created_at": "2026-11-17T10:00:00Z"
    }
  ],
  "pagination": { ... }
}
```

**Кэширование:** 120 секунд.

### Gallery Detail

```
GET /api/v1/gallery/{id}/
```

**Response body — `data`:**
```json
{
  "id": 1,
  "title": "Photo Title",
  "description": "Photo description",
  "image": "https://example.com/media/gallery/2026/11/photo.jpg",
  "thumbnail": "https://example.com/media/gallery/thumb_/photo.jpg",
  "category": {
    "id": 1,
    "title": "Tech",
    "slug": "tech"
  },
  "is_active": true,
  "created_at": "2026-11-17T10:00:00Z"
}
```

## Comments API

### List Comments

```
GET /api/v1/pages/{page_id}/comments/
```

**Response body — `data`:**
```json
{
  "items": [...],
  "pagination": { ... }
}
```

Элемент комментария:
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "",
  "text": "Great article!",
  "status": "approved",
  "is_spam": false,
  "author": { "id": 5, "username": "john" },
  "page": { "id": 1, "title": "My Page", "slug": "my-page" },
  "parent": null,
  "reply_count": 2,
  "replies": [
    {
      "id": 3,
      "name": "Reply Author",
      "text": "Thanks!",
      "reply_count": 0,
      "parent": 1,
      "created_at": "2026-11-17T11:00:00Z"
    }
  ],
  "created_at": "2026-11-17T10:30:00Z"
}
```

**Кэширование:** 2 минуты по ключу `comments:{slug}`.

**Важно:** Используется `active_objects` менеджер (фильтр: `status='approved', is_spam=False`). Пагинация применяется корректно.

### Submit Comment

```
POST /api/v1/pages/{page_id}/comments/submit/
Content-Type: application/json
{
  "name": "John Doe",
  "email": "john@example.com",
  "text": "Great article!",
  "honeypet": ""
}
```

**Валидация:**
- `honeypot` поле должно быть **пустым** (для защиты от ботов — скрытое honeypot поле в HTML-форме)
- `text` не может быть `honeypot` значением (защита от простых ботов)
- `page_id` must exist

**Response на успешную submit:**
```json
{
  "success": true,
  "data": {
    "message": "Comment submitted successfully. It will appear after moderation.",
    "comment": { ... }
  }
}
```

**Response на ошибку:**
```json
{
  "success": false,
  "error": { "code": "honeypot_filled", "detail": "Error message" }
}
```

При успехе запускается Celery задача `send_email_notification(comment_id)`.

## Admin Stats

```
GET /api/v1/admin/stats/
```

Только для авторизованных пользователей (`@login_required`).

**Response body — `data`:**
```json
{
  "total_pages": 150,
  "published_pages": 120,
  "draft_pages": 30,
  "total_comments": 340,
  "pending_comments": 12,
  "approved_comments": 310,
  "rejected_comments": 10,
  "spam_comments": 50,
  "total_views": 15234,
  "total_categories": 8,
  "total_subscribers": 45,
  "active_subscribers": 32,
  "top_pages": [
    {
      "title": "Most Read Page",
      "views": 1500
    }
  ],
  "recent_pages": [...],
  "recent_comments": [...]
}
```

**Top pages:** `annotate(total_views=Count('view_count')).order_by('-total_views')[:10]`

**Recent pages/comments:** `order_by('-created_at')[:10]`

## Sitemap (Public)

```
GET /sitemap.xml
GET /sitemap/
```

Генерирует `<urlset>` с приоритетами:
| URL | Priority |
|---|---|
| `/` | 0.9 |
| `/pages/` | 0.8 |
| `/gallery/` | 0.7 |
| `/category/*` | 0.6 |
| `/page/*` | 0.5 |

И использует `Page.published_objects.iterator(chunk_size=...)` для памяти.

## Robots.txt

```
GET /robots.txt

User-agent: *
Allow: /
Sitemap: https://example.com/sitemap.xml
```

## URL Summary

| Method | URL | Description | Auth Required | Cached |
|---|---|---|---|---|
| GET | `/api/` | API index | No | No |
| GET | `/api/health/` | Health check | No | No |
| GET | `/api/v1/pages/` | List pages | No | 60s |
| GET | `/api/v1/pages/{id}/` | Page detail | No | 120s |
| GET | `/api/v1/categories/` | List categories | No | 60s |
| GET | `/api/v1/gallery/` | List gallery | No | 120s |
| GET | `/api/v1/gallery/{id}/` | Gallery detail | No | No |
| GET/POST | `/api/v1/pages/{id}/comments/` | Comments | No | 120s |
| POST | `/api/v1/pages/{id}/comments/submit/` | Submit comment | No | No |
| GET | `/api/v1/admin/stats/` | Admin stats | Yes | No |

## Internal (Non-API) Views

| Method | URL | Description | Auth |
|---|---|---|---|
| GET | `/` | Home | No |
| GET | `/pages/` | Page list (paginated) | No |
| GET | `/page/{slug}/` | Page detail | No |
| GET | `/category/{slug}/` | Category detail | No |
| GET/POST | `/subscribe/` | Subscribe | No |
| GET | `/unsubscribe/{id}/` | Unsubscribe | No |
| GET | `/gallery/` | Gallery list | No |
| GET | `/gallery/{id}/` | Gallery detail | No |
| GET/POST | `/create/` | Create page | Yes |
| GET/POST | `/pages/{slug}/edit/` | Edit page | Yes |
| GET/POST | `/pages/{slug}/delete/` | Delete page | Yes |
| GET/POST | `/blocks/create/{slug}/` | Create block | Yes |
| GET/POST | `/blocks/{id}/delete/` | Delete block | Yes |
| GET/POST | `/categories/create/` | Create category | Yes |
| GET/POST | `/categories/{slug}/edit/` | Edit category | Yes |
| GET/POST | `/categories/{slug}/delete/` | Delete category | Yes |
| GET/POST | `/page/{slug}/comment/` | Add comment | No |
| GET/POST | `/page/{slug}/comment/{id}/reply/` | Add reply | No |
