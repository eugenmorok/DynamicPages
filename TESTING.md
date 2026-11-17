# TESTING — DynamicPages

Руководство по тестированию проекта на основе фактического содержимого `pages/tests.py`.

## Запуск тестов

```bash
# Все тесты
python manage.py test pages

# Верbose (видно каждый тест)
python manage.py test pages --verbosity=2

# Один тестовый класс
python manage.py test pages.PageModelTestCase

# Один тест
python manage.py test pages.PageModelTestCase.test_published_objects

# Проверка проекта (не тесты)
python manage.py check
```

## Обзор

- **Файл**: `pages/tests.py`
- **Всего тестов**: 31
- **Тестируемых классов**: 9
- **База данных**: Django test framework (использует DATABASE_URL из settings, в тестировании SQLite или PostgreSQL)
- **Фикстуры**: `setUpTestData()` (созданы один раз на весь класс), `setUp()` (если есть)

## Helper

```python
def _make_fake_image(name="test.png", size=10):
    """Создаёт InMemoryUploadedFile с PNG-изображением размером size×size."""
    img = PILImage.new('RGB', (size, size), color='red')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return InMemoryUploadedFile(buf, 'image', name, 'image/png', buf.getbuffer().nbytes, None)
```

Используется в тестировании MediaGallery для предоставления fake-изображений.

## Тестовые классы

### 1. PageModelTestCase — тестирование модели Page (2 теста)

**Setup:**
- Страница `Test Page` (`slug=test-page`, `status=published`, `status=Page.PUBLISHED`)
- Страница `Draft Page` (`slug=draft-page`, `status=Page.DRAFT`)
- Категория `TestCategory` (`slug=test-cat`)

**Тесты:**

| # | Метод | Что проверяет | Ожидаемый результат |
|---|---|---|---|
| 1 | `test_published_objects` | `Page.published_objects.count()` | 1 (только published); draft не включён |
| 2 | `test_published_objects` | `self.page in Page.published_objects.all()` | Страница находится в published |
| 3 | `test_increment_view_count` | Атомарный инкремент `view_count` | Устанавливает 0, сохраняет, вызывает `increment_view_count()`, проверяет что `view_count == 1` |

---

### 2. PageCategoryTestCase — тестирование модели PageCategory (4 теста)

**Тесты:**

| # | Метод | Что проверяет | Ожидаемый результат |
|---|---|---|---|
| 1 | `test_slug_generation` | Auto-slug при создании | `category.slug.lower().replace('-', '')` == `'autoslugtest'` |
| 2 | `test_is_active_default` | Значение по умолчанию `is_active` | `True` |
| 3 | `test_page_count` | Связь `PageCategory.pages.count()` | 1 страница в категории |
| 4 | `test_page_objects_relationship` | Связь `cat.pages.all()` | Страница в `cat.pages.all()` |

---

### 3. CommentTestCase — тестирование модели Comment (3 теста)

**Setup:**
- Страница `Comments Page` (`slug=comments-page`, `status=published`)

**Тесты:**

| # | Метод | Что проверяет | Ожидаемый результат |
|---|---|---|---|
| 1 | `test_creation` | Создание комментария, `comment.page_id`, `is_spam` | `page_id` совпадает, `is_spam == False` |
| 2 | `test_status_default` | Статус по умолчанию | `'pending'` |
| 3 | `test_get_approved` | Фильтрация `Comment.approved_objects.filter(page=...)` | 1 approved, 1 pending — возвращается только approved |

---

### 4. MediaGalleryTestCase — тестирование модели MediaGallery (2 теста)

**Setup:**
- Категория `Gallery` (`slug=gallery`)
- `active_item` — `is_active=True`, с fake-изображением
- `inactive_item` — `is_active=False`, с fake-изображением `inactive.png`

**Тесты:**

| # | Метод | Что проверяет | Ожидаемый результат |
|---|---|---|---|
| 1 | `test_active_objects` | `MediaGallery.active_objects.all()` | Содержит `active_item`, НЕ содержит `inactive_item` |
| 2 | `test_inactive_filtered_out` | `MediaGallery.active_objects.count()` | 1 |

---

### 5. SiteSettingTestCase — тестирование модели SiteSetting (2 теста)

**Тесты:**

| # | Метод | Что проверяет | Ожидаемый результат |
|---|---|---|---|
| 1 | `test_get_set_value` | `SiteSetting.get_value('site_title')` | Возвращает значение из БД |
| 2 | | `SiteSetting.get_value('missing_key', 'fallback')` | Возвращает fallback |
| 3 | `test_cache_usage` | `cache.clear()` + двойной вызов `get_value` | `val1 == val2` (второй вызов берёт из кэша) |

---

### 6. ViewsTestCase — тестирование view функций (5 тестов)

**Setup:**
- Категория `View Cat` (`slug=view-cat`)
- Страница `Home Test Page` (`slug=home-test`, `status=published`, `excerpt='Home page'`)
- `self.client = Client()`

**Тесты:**

| # | Метод | URL | что проверяет |
|---|---|---|---|
| 1 | `test_home` | `/` | `resp.status_code == 200`; `resp` содержит 'home' |
| 2 | `test_page_detail` | `/page/home-test/` | `200` |
| 3 | `test_category_detail` | `/category/view-cat/` | `200` |
| 4 | `test_not_found` | `/page/nonexistent/` | `404` |
| 5 | `test_page_list` | `/pages/` | `200` |

---

### 7. APITestCase — тестирование REST API (9 тестов)

**Setup:**
- Категория `APICat` (`slug=api-cat`)
- Страница `API Test Page` (`slug=api-test-page`, `status=published`)
- Элемент галереи `API Gallery` (`is_active=True`)
- Комментарий `TestUser` (`status=approved`)

**Тесты:**

| # | Метод | URL | что проверяет |
|---|---|---|---|
| 1 | `test_health` | `GET /api/health/` | `200`; `data['status'] == 'healthy'` |
| 2 | `test_api_index` | `GET /api/` | `200`; `data` содержит `version` |
| 3 | `test_api_pages_list` | `GET /api/v1/pages/` | `200`; `data['pagination']['total'] >= 1` |
| 4 | `test_api_page_detail` | `GET /api/v1/pages/{pk}/` | `200`; `data['title'] == 'API Test Page'` |
| 5 | `test_api_categories` | `GET /api/v1/categories/` | `200`; `len(data) == 1` |
| 5 | `test_api_categories` | `GET /api/v1/categories/` | `200`; `len(data) == 1` |
| 6 | `test_api_gallery` | `GET /api/v1/gallery/` | `200`; `data['pagination']['total'] == 1` |
| 7 | `test_api_gallery_detail` | `GET /api/v1/gallery/{pk}/` | `200`; `data['title'] == 'API Gallery'` |
| 8 | `test_api_comments` | `GET /api/v1/pages/{page_id}/comments/` | `200`; `data['total'] == 1` |
| 9 | `test_api_comment_submit` | `POST /api/v1/pages/{page_id}/comments/submit/` (JSON body) | `201`; `data['status'] == 'pending'` |

---

### 8. CacheTestCase — тестирование кэширования (1 тест)

**Setup:**
- Страница `Cache Test` (`slug=cache-test`, `status=published`)

**Тесты:**

| # | Метод | Что проверяет |
|---|---|---|
| 1 | `test_invalidation` | `cache.set(cache_key, data)` → `cache.get()` возвращает данные → `cache.delete()` → `cache.get()` возвращает `None` |

---

### 9. SubscriptionTestCase — тестирование модели Subscription (2 теста)

**Тесты:**

| # | Метод | Что проверяет |
|---|---|---|
| 1 | `test_creation` | `Subscription.objects.create(email='test@sub.com')` → `active == True`; `str(sub) == 'test@sub.com (True)'` |
| 2 | `test_unique_email` | Два создания одного email → `exception` (UNIQUE constraint violation) |

---

### 10. PerformanceTestCase — тестирование производительности (1 тест)

**Setup (20 опубликованных страниц):**
```python
now = timezone.now()
cls.pages = Page.objects.bulk_create([
    Page(title=f'Perf Page {i}', slug=f'perf-page-{i}', category=cls.category, status='published', published_at=now)
    for i in range(20)
])
```

**Тесты:**

| # | Метод | Что проверяет |
|---|---|---|
| 1 | `test_bulk_filtering_efficiency` | `Page.published_objects.select_related('category').filter(category=cat)` при 20 страницах → количество queried ≤ 5 |

Используется `CaptureQueriesContext` для захвата SQL-запросов. Цель: проверить что eager loading (`select_related`) предотвращает N+1 запросы.

## Итого: 31 тест

| Тестовый класс | Кол-во тестов | Что покрывает |
|---|---|---|
| `PageModelTestCase` | 3 | `published_objects`, `increment_view_count()` |
| `PageCategoryTestCase` | 4 | slug_gen, default_active, page_count, relationships |
| `CommentTestCase` | 3 | creation, status_default, approved_objects filter |
| `MediaGalleryTestCase` | 2 | active_objects filter (active/inactive) |
| `SiteSettingTestCase` | 2 | get_value, cache_behavior |
| `ViewsTestCase` | 5 | home, page_detail, category_detail, 404, page_list |
| `APITestCase` | 9 | health, index, pages_list, pages_detail, categories, gallery_list, gallery_detail, comments, comment_submit |
| `CacheTestCase` | 1 | set/get/delete invalidation |
| `SubscriptionTestCase` | 2 | creation, unique_email |
| `PerformanceTestCase` | 1 | select_related N+1 prevention (≤ 5 queries) |
| **Итого** | **31** | |

## Coverage по коду

| Компонент | Тестируется? | Примечания |
|---|---|---|
| `Page.views_count` (models.py) | ✅ | `test_increment_view_count` |
| `Page.published_objects` (managers.py) | ✅ | `test_published_objects` |
| `PageCategory` (models.py) | ✅ | `PageCategoryTestCase` (4 теста) |
| `PageBlock` (models.py) | ❌ | Нет тестов |
| `SiteSetting` (models.py) | ✅ | `test_get_set_value`, `test_cache_usage` |
| `Comment.active_objects` | ✅ | `test_get_approved` |
| `MediaGallery.active_objects` | ✅ | `test_active_objects`, `test_inactive_filtered_out` |
| `Subscription` (models.py) | ✅ | `test_creation`, `test_unique_email` |
| Views (views.py) | ✅ | `test_home`, `test_page_detail`, `test_category_detail`, `test_not_found`, `test_page_list` |
| API (api.py) | ✅ | 9 тестов API-эндпоинтов |
| Rate limiting (rate_limiting.py) | ❌ | Нет тестов |
| Monitoring (monitoring.py) | ❌ | Нет тестов |
| Consumers (consumers.py) | ❌ | Нет тестов |
| Sitemaps (sitemaps.py) | ❌ | Нет тестов |
| Email/Signals (signals.py) | ❌ | Нет тестов |
| Forms (forms.py) | ❌ | Нет тестов |

## Типы тестов

| Класс Django | Используется | Цели |
|---|---|---|
| `TestCase` | ✅ | 28 тестов (model, view, integration) |
| `SimpleTestCase` | ❌ | |
| `TransactionTestCase` | ❌ | |

## Структура набора тестов

```
pages/tests.py (379 строк)
├─ helper: _make_fake_image()
├─ PageModelTestCase (setup: 1 published + 1 draft page + 1 category)
├─ PageCategoryTestCase
├─ CommentTestCase (setup: 1 published page)
├─ MediaGalleryTestCase (setup: category + 2 items with fake images)
├─ SiteSettingTestCase
├─ ViewsTestCase (setup: category + published page + Client())
├─ APITestCase (setup: category + page + gallery + comment)
├─ CacheTestCase (setup: 1 published page)
├─ SubscriptionTestCase
└─ PerformanceTestCase (setup: category + 20 pages via bulk_create)
```
