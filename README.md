# DynamicPages — CMS на Django

Динамическая CMS с поддержкой страниц, категорий, блоков контента, комментариев, подписок, медиагалереи и REST API.

## Стек технологий

| Компонент | Технология |
|---|---|
| Фреймворк | Django 5.2.19 |
| CMS / Текст | django-ckeditor-5 |
| Frontend | Bootstrap 5.3.2, Font Awesome 6.7.2 |
| База данных | PostgreSQL (production) / SQLite (development) |
| Брокер задач | Celery + Redis |
| WebSocket | Django Channels + channels_redis |
| Кэширование | Redis (production) / locmem (development) |
| Статика | WhiteNoise |
| Конфигурация | django-environ (.env) |
| HTTPS / CSP | django-csp |

## Быстрый старт

```bash
# 1. Клонирование
git clone https://github.com/eugenmorok/DynamicPages.git
cd DynamicPages

# 2. Виртуальное окружение
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux/macOS

# 3. Зависимости
pip install -r requirements.txt

# 4. .env (настройка окружения см. ниже)
cp .env.example .env             # если есть
nano .env

# 5. Migrations
python manage.py makemigrations pages
python manage.py migrate

# 6. Суперпользователь
python manage.py createsuperuser

# 7. Запуск сервера
python manage.py runserver

# 8. Celery worker (для асинхронных задач)
celery -A dynamicpages worker -l info

# 9. Celery beat (для периодических задач)
celery -A dynamicpages beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Настройка окружения (.env)

```env
DEBUG=1

# ============================================
# Database: PostgreSQL production / SQLite dev
# ============================================
# PostgreSQL (production):
DATABASE_URL=postgresql://user:pass@localhost:5432/dynamicpages

# Или SQLite (development — используется автоматически при отсутствии DATABASE_URL):
# DATABASE_URL=sqlite:///db.sqlite3

# ============================================
# Redis (caching, Celery broker, Channels)
# ============================================
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CHANNELS_DEFAULT_REDIS_URL=redis://localhost:6379/1

# ============================================
# Django
# ============================================
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Структура проекта

```
DynamicPages/
├─ manage.py                        # CLI Django
├─ dynamicpages/                    # Корневое приложение (settings, urls, wsgi)
│  ├─ settings.py                   # 421 строка: DB, cache, celery, CSP, channels
│  ├─ urls.py                       # URL root: admin, ckeditor5, API v1, pages app
│  ├─ wsgi.py / asgi.py
├─ pages/                           # Основное приложение
│  ├─ models.py                     # 7 моделей (Page, PageCategory, PageBlock, etc.)
│  ├─ managers.py                   # 3 кастомных менеджера
│  ├─ views.py                      # Функции + классы (CRUD, search, gallery)
│  ├─ forms.py                      # PageForm, CategoryForm, CommentForm, SearchForm
│  ├─ urls.py                       # 65 URL-паттернов
│  ├─ api.py                        # REST API (495 строк)
│  ├─ tasks.py                      # 4 Celery-задачи
│  ├─ consumers.py                  # 3 WebSocket consumers
│  ├─ signals.py                    # post_save / post_delete (кэш)
│  ├─ admin.py                      # PageAdmin с bulk-actions
│  ├─ rate_limiting.py              # 154 строки: SimpleRateLimiter + RateLimitMiddleware
│  ├─ monitoring.py                 # 179 строк: PerformanceMiddleware + metrics
│  ├─ sitemaps.py                   # 4 sitemap generators
│  ├─ context_processors.py         # common_settings(request)
│  ├─ tests.py                      # 31 тест (6 классов)
│  ├─ migrations/                   # 4 миграции
│  │  ├─ 0001_initial.py           # PageCategory, SiteSetting, Page, PageBlock
│  │  ├─ 0002_subscription_comment_mediagallery.py  # Subscription, Comment, MediaGallery
│  │  ├─ 0003_remove_page_content...  # content → default (CKEditor5Field)
│  │  └─ 0004_mediagallery_thumbnail... # thumbnail + covering indexes
│
├─ templates/
│  ├─ base.html                     # Bootstrap navbar + footer (149 строк)
│  ├─ home.html                     # Hero, categories, recent pages
│  ├─ pages/
│  │  ├─ detail.html             # Страница: контент, блоки, комментарии
│  │  ├─ list.html               # Список + поиск + пагинация
│  │  ├─ form.html               # Создание/редактирование страницы
│  │  ├─ category_detail.html    # Категория + страницы
│  │  ├─ gallery.html            # Галерея
│  │  └─ gallery_detail.html     # Одно изображение
│  └─ registration/               # Login, logout, password reset
├─ static/
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ LICENSE
```

## Запуск тестов

```bash
python manage.py test pages --verbosity=2
python manage.py check
```

**31 тест** в 6 тестовых классах. Все проходят.

## URL-структура

### Public-маршруты (pages/urls.py)

| Method | URL | View | Описание |
|---|---|---|---|
| `GET` | `/` | `home` | Главная страница |
| `GET` | `/pages/` | `PageListView` | Список страниц (Class-based) |
| `GET` | `/page/<slug:slug>/` | `page_detail` | Страница (с комментариями) |
| `GET` | `/category/<slug:slug>/` | `category_detail` | Категория + страницы |
| `GET`, `POST` | `/subscribe/` | `subscribe` | Подписка по email |
| `GET` | `/unsubscribe/<int:pk>/` | `unsubscribe` | Отписка |
| `GET` | `/gallery/` | `gallery_list` | Галерея |
| `GET` | `/gallery/<int:pk>/` | `gallery_detail` | Одно изображение |
| `GET` | `/sitemap.xml` | `sitemap_xml` | Sitemap |
| `GET` | `/robots.txt` | `robots_txt` | Robots.txt |

### CRUD (авторизованные, login_required)

| Method | URL | Описание |
|---|---|---|
| `GET`, `POST` | `/create/` | Создать страницу |
| `GET`, `POST` | `/pages/<slug>/edit/` | Редактировать |
| `GET`, `POST` | `/pages/<slug>/delete/` | Удалить |
| `GET`, `POST` | `/blocks/create/<slug>/` | Создать блок |
| `GET`, `POST` | `/blocks/<int:pk>/delete/` | Удалить блок |
| `GET`, `POST` | `/categories/create/` | Создать категорию |
| `GET`, `POST` | `/categories/<slug>/edit/` | Редактировать категорию |
| `GET`, `POST` | `/categories/<slug>/delete/` | Удалить категорию |

### Комментарии

| Method | URL | Описание |
|---|---|---|
| `GET`, `POST` | `/page/<slug>/comment/` | Добавить комментарий |
| `GET`, `POST` | `/page/<slug>/comment/<pk>/reply/` | Ответить на комментарий |

### REST API v1 (dynamicpages/urls.py)

| Method | URL | Описание |
|---|---|---|
| `GET` | `/api/health/` | Health check |
| `GET` | `/api/` | Индекс API (список эндпоинтов) |
| `GET` | `/api/v1/pages/` | Список страниц |
| `GET` | `/api/v1/pages/<int:pk>/` | Детали страницы |
| `GET` | `/api/v1/categories/` | Список категорий |
| `GET` | `/api/v1/gallery/` | Список галереи |
| `GET` | `/api/v1/gallery/<int:pk>/` | Детали галереи |
| `GET`, `GET`, `POST` | `/api/v1/pages/<int:page_id>/comments/` | Получить/отправить комментарии |
| `GET` | `/api/v1/pages/<int:page_id>/comments/submit/` | Отправить комментарий |
| `GET` | `/api/v1/admin/stats/` | Статистика для админки |

## Админ-панель

Управлять контентом через `/admin/`:

- **Pages** — создание/редактирование страниц, bulk-approves/rejects комментариев
- **Categories** — управление категориями
- **Comments** — модерация с bulk-actions (approve/reject/spam/move_to_spam)
- **Subscriptions** — управление подписками
- **PageBlocks** — блоки страниц (inline)
- **MediaGallery** — медиагалерея
- **SiteSettings** — настройки сайта (ключ-значение)

## Production-настройки (settings.py)

```env
# Кэширование (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': redis_url,
    }
}

# Celery (broker + backend)
CELERY_BROKER_URL = redis_url
CELERY_RESULT_BACKEND = redis_url

# Channels (channel_layer)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [redis_url]},
    }
}

# CSRF trusted origins (Vercel frontend)
CSRF_TRUSTED_ORIGINS = [
    'https://dynamicpages-frontend.vercel.app',
]

# CSP (Content-Security-Policy)
CSP = {
    'DIRECTIVES': {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", ...],
        'style-src': ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net", ...],
        'img-src': ["'self'", "data:", "https:", "..."],
        # etc.
    }
}
```

## Асинхронные задачи (Celery tasks)

| Задача | Описание | Повторные попытки |
|---|---|---|
| `generate_thumbnail(gallery_id)` | Генерация миниатюры 120x120 (Pillow) | 3 раза, каждые 60с |
| `send_email_notification(comment_id)` | Email уведомление на site_email с текстом комментария | 5 раз, каждые 30с |
| `send_subscription_digest()` | Еженедельный дайджест новых страниц для подписчиков | Нет |
| `cleanup_old_subscriptions()` | Удаление неактивных подписок старше 2 лет | Нет |
| `analytics_aggregate(start_date, end_date)` | Агрегация статистики (top pages, most commented) | Нет |

## Модельная схема (7 моделей)

### Page (главная)

| Поле | Тип | Описание |
|---|---|---|
| title | CharField(300) | Заголовок |
| slug | SlugField(300) | Уникальный URL-адрес |
| default | CKEditor5Field | Контент (Rich Text) |
| excerpt | TextField(500) | Краткое описание |
| meta_title | CharField(200) | SEO meta title |
| meta_description | TextField(500) | SEO meta description |
| meta_keywords | CharField(300) | SEO keywords через запятую |
| featured_image | ImageField | Обложка |
| status | CharField | published / draft |
| published_at | DateTimeField | Дата публикации |
| is_featured | BooleanField | Рекомендуемая |
| view_count | PositiveIntegerField | Счётчик просмотров |
| author | ForeignKey(User) | Автор |
| category | ForeignKey(PageCategory) | Категория |
| blocks | reverse FK | Блоки страницы |
| comments | reverse FK | Комментарии |

**Кастомный метод:**
- `increment_view_count()` — атомарный `F('view_count') + 1`

**Кастомные менеджеры:**
- `objects` — стандартный
- `published_objects` — только опубликованные (`status='published'`, `published_at__lte=now`), с `select_related(category, author)` + `prefetch_related(blocks)`

**Кастомные индексы (Meta.indexes):**
1. `(title, slug)` — составной
2. `(status, published_at)` — для фильтрации
3. `(category, status)` — для поиска по категории
4. `(is_featured, published_at)` — featured pages
5. `(status, published_at, title, slug, category_id)` — covering index для списка

---

### PageCategory

| Поле | Тип | Описание |
|---|---|---|
| title | CharField(200, db_index) | Название |
| slug | SlugField(200, unique) | URL-адрес |
| description | TextField | Описание |
| is_active | BooleanField(default=True) | Активна |
| pages | reverse FK | Страницы категории |

---

### PageBlock

| Поле | Тип | Описание |
|---|---|---|
| title | CharField(200) | Заголовок блока |
| default | CKEditor5Field | Контент блока |
| image | ImageField | Изображение блока |
| ordering | PositiveSmallIntegerField | Порядок сортировки |
| page | FK(Page) | Родительская страница |

---

### Comment

| Поле | Тип | Описание |
|---|---|---|
| text | TextField(5000) | Текст комментария |
| status | CharField | pending / approved / rejected |
| is_spam | BooleanField | Спам-флаг |
| name | CharField(100) | Имя |
| email | EmailField | Email (не публикуется) |
| author | FK(User, null=True) | Автор-юзер |
| page | FK(Page) | Страница |
| parent | FK(Comment, null=True) | Родительский комментарий (реплаи) |
| replies | reverse FK | Ответы на комментарий |

**Менеджер:**
- `objects` — стандартный
- `active_objects` — `status='approved' AND is_spam=False`, с `select_related(author, page)`
- Алиас: `approved_objects = active_objects` (для обратной совместимости)

**Покрытые индексы:**
1. `(page, status)` — для списка комментариев
2. `(page, -created_at)` — для сортировки по дате
3. `(status, -created_at)` — для модерации
4. `(page, status, created_at, text, name, author_id)` — covering index для поиска
---

### Subscription

| Поле | Тип | Описание |
|---|---|---|
| email | EmailField(unique, db_index) | Email подписчика |
| active | BooleanField(default=True) | Активна |

**Индекс:** `(email, active)`

---

### MediaGallery

| Поле | Тип | Описание |
|---|---|---|
| title | CharField(200) | Заголовок |
| description | TextField | Описание |
| image | ImageField | Изображение gallery/%Y/%m/ |
| thumbnail | ImageField | Миниатюра gallery/thumbs/%Y/%m/ |
| is_active | BooleanField(default=True) | Активна |
| category | FK(PageCategory) | Категория |
| category.gallery | reverse FK | Галерея категории |

**Менеджер `active_objects`:** `is_active=True`, `select_related(category)`, `order_by(-created_at)`

**Индексы:**
1. `(is_active, -created_at)` — для списка
2. `(category, is_active, created_at)` — covering index

---

### SiteSetting

| Поле | Тип | Описание |
|---|---|---|
| key | CharField(50, unique) | Ключ (site_title, etc.) |
| value | TextField | Значение |
| label | CharField(100) | Human-readable label |

**Choices на ключ:**
`site_title, site_description, site_email, site_phone, site_address, facebook_url, twitter_url, instagram_url, youtube_url, analytics_id, custom_css`
