# MIGRATIONS — Эволюция базы данных

Полная история миграций приложения `pages`. Файлы в `pages/migrations/`.

## Список миграций

### 0001_initial.py — Начальная схема
**Дата**: 2026-11-12 07:42  
**Зависимости**: Django auth user model (swappable dependency)

Создаёт базовые модели:

| Модель | Таблица | Поля |
|---|---|---|
| `PageCategory` | `pages_pagecategory` | id, title (db_index), slug (unique), description, created_at, updated_at, is_active |
| `SiteSetting` | `pages_sitesetting` | id, key (unique + choices), value (TextField), label, updated_at |
| `Page` | `pages_page` | id, title (db_index), slug (unique), **content** (RichTextUploadingField), excerpt, meta_title, meta_description, meta_keywords, featured_image (upload_to='pages/%Y/%m/'), status (published/draft), created_at, updated_at, published_at, is_featured, view_count, author (FK→User), category (FK→PageCategory CASCADE) |
| `PageBlock` | `pages_pageblock` | id, title, **content** (RichTextUploadingField), image (upload_to='blocks/%Y/%m/'), ordering, created_at, page (FK→Page CASCADE) |

**Индексы (AddIndex):**
| Название | Поля |
|---|---|
| `pages_page_title_e48630_idx` | `[title, slug]` |
| `pages_page_status_de97e2_idx` | `[status, published_at]` |
| `pages_page_categor_eecb72_idx` | `[category, status]` |

**Options:**
- PageCategory: ordering=['title'], verbose='Категория страницы'
- Page: ordering=['-published_at'], verbose='Страница'
- PageBlock: ordering=['ordering'], verbose='Блоки страницы'

---

### 0002_subscription_comment_mediagallery.py — Подписки, комментарии, галерея
**Дата**: 2026-11-16 15:07  
**Зависимости**: `pages.0001_initial` + Django auth

Создаёт 3 дополнительные модели:

| Модель | Таблица | Поля |
|---|---|---|
| `Subscription` | `pages_subscription` | id, email (unique + db_index), active, created_at |
| `Comment` | `pages_comment` | id, email, name, text (max_length=5000), status (pending/approved/rejected), is_spam, created_at, updated_at, author (FK→User SET_NULL), page (FK→Page CASCADE), parent (FK→Comment CASCADE, nullable) |
| `MediaGallery` | `pages_mediagallery` | id, title, description (default=''), image (upload_to='gallery/%Y/%m/'), created_at, updated_at, is_active, category (FK→PageCategory SET_NULL, nullable) |

**Индексы (indexes в Meta.options):**
| Название | Поля | Модель |
|---|---|---|
| `pages_subsc_email_11932c_idx` | `[email, active]` | Subscription |
| `pages_comme_page_id_72a894_idx` | `[page, status]` | Comment |
| `pages_comme_page_id_79a1fb_idx` | `[page, -created_at]` | Comment |
| `pages_comme_status_20f724_idx` | `[status, -created_at]` | Comment |
| `pages_media_is_acti_a80ea3_idx` | `[is_active, -created_at]` | MediaGallery |

---

### 0003_remove_page_content_remove_pageblock_content_and_more.py — content → default
**Дата**: 2026-11-17 08:38  
**Зависимости**: `pages.0002_subscription_comment_mediagallery`

**ВАЖНО**: Переименование `content` → `default` — критическая migration.
- Поле **`content`** (`RichTextUploadingField`) используется `django-ckeditor-uploader`
- Переименование в **`default`** (`CKEditor5Field`) — переход на `django-ckeditor-5`
- Это требует обновления кода: все `page.content` → `page.default`

**Операции:**
| Тип | Модель | Поле | Новая/старая value |
|---|---|---|---|
| **RemoveField** | `page` | `content` | `RichTextUploadingField` → удалено |
| **RemoveField** | `pageblock` | `content` | `RichTextUploadingField` → удалено |
| **AddField** | `page` | `default` | `CKEditor5Field(blank=True, verbose='Содержание')` |
| **AddField** | `pageblock` | `default` | `CKEditor5Field(blank=True, verbose='Содержание')` |

**Двойной эффект:**
1. БД: старая колонка `content` удалена, новая `default` добавлена
2. Код: все упоминания `.content` сломались до обновления кода (фикс в Stage 5b)

---

### 0004_mediagallery_thumbnail_comment_covering_indexes.py — Миниатюры и covering indexes
**Дата**: 2026-11-17 09:14  
**Зависимости**: `pages.0003_remove_page_content_...` + Django auth

Добавляет поле `thumbnail` для MediaGallery и покрывающие индексы.

**Операции:**

| Тип | Модель | Детали |
|---|---|---|
| **AddField** | `mediagallery` | `thumbnail = ImageField(upload_to='gallery/thumbs/%Y/%m/')` для генерации миниатюр |
| **AddIndex** | `comment` | `[page, status, created_at, text, name, author_id]` = **`comment_meta_covering`** — covering index для комментариев |
| **AddIndex** | `mediagallery` | `[category, is_active, created_at]` = **`gallery_category_covering`** — covering index для галереи |
| **AddIndex** | `page` | `[is_featured, published_at]` = **`featured_pages_idx`** — для featured pages |
| **AddIndex** | `page` | `[status, published_at, title, slug, category_id]` = **`page_list_covering`** — covering index для списка pages |

## Итоговая схема индексов

### Page (`pages_page`)

| # | Имя | Поля | Откуда |
|---|---|---|---|
| 1 | `pages_page_title_e48630_idx` | `[title, slug]` | 0001 |
| 2 | `pages_page_status_de97e2_idx` | `[status, published_at]` | 0001 |
| 3 | `pages_page_categor_eecb72_idx` | `[category, status]` | 0001 |
| 4 | `featured_pages_idx` | `[is_featured, published_at]` | 0004 |
| 5 | `page_list_covering` | `[status, published_at, title, slug, category_id]` | 0004 (covering) |

### PageCategory (`pages_pagecategory`)

Без кастомных индексов (кроме db_index на field `title` в модели).

### PageBlock (`pages_pageblock`)

Без кастомных индексов.

### Comment (`pages_comment`)

| # | Имя | Поля | Откуда |
|---|---|---|---|
| 1 | `pages_comme_page_id_72a894_idx` | `[page, status]` | 0002 |
| 2 | `pages_comme_page_id_79a1fb_idx` | `[page, -created_at]` | 0002 |
| 3 | `pages_comme_status_20f724_idx` | `[status, -created_at]` | 0002 |
| 4 | `comment_meta_covering` | `[page, status, created_at, text, name, author_id]` | 0004 (covering) |

### Subscription (`pages_subscription`)

| # | Имя | Поля | Откуда |
|---|---|---|---|
| 1 | `pages_subsc_email_11932c_idx` | `[email, active]` | 0002 |

### MediaGallery (`pages_mediagallery`)

| # | Имя | Поля | Откуда |
|---|---|---|---|
| 1 | `pages_media_is_acti_a80ea3_idx` | `[is_active, -created_at]` | 0002 |
| 2 | `gallery_category_covering` | `[category, is_active, created_at]` | 0004 (covering) |

### SiteSetting (`pages_sitesetting`)

Без кастомных индексов (ключ `key` уже unique, что достаточно для lookup).

## Хронология изменеий базы

```
0001 (2026-11-12)    — Init: PageCategory, SiteSetting, Page, PageBlock + 3 индекса
0002 (2026-11-16)    — Subscription, Comment, MediaGallery + 5 индексов
0003 (2026-11-17)    — content → default (CKEditor5Field)
0004 (2026-11-17)    — thumbnail + 4 covering/powered indexes
                        = featured_pages index + page_list_covering + comment_meta_covering + gallery_category_covering
```

## Совокупность

- Всего индексов: **3 (from 0001) + 5 (from 0002) + 4 (from 0004) = 12**
- Поля models.py `Meta.indexes` не нужны — все индексы через миграции
- Покрытие: 5 covering indexes for `page`, `comment`, `gallery`, `subscription`, `featured_pages`
- Покрытие индекса на `page` используется `Page.published_objects` + `PageListView`
- Покрытие индекса на `comment` используется `Comment.approved_objects`, `active_objects`
