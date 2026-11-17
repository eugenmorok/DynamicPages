# DynamicPages — Django + PostgreSQL

Динамический сайт с системой управления страницами, категориями и админ-панелью.

## 🚀 Возможности

### Публичные возможности
- **Динамические страницы** — создание, редактирование, удаление через админ-панель
- **Категории** — группировка страниц по разделам
- **SEO-оптимизация** — meta tags (title, description, keywords) для каждой страницы
- **Поиск** — полнотекстовый поиск по заголовкам, описаниям и содержанию
- **Редактирование контента** — визуальный редактор CKEditor с загрузкой изображений
- **Изображения** — загрузка и отображение featured-изображений
- **Просмотры** — счётчик просмотров для каждой страницы
- **Поделиться** — кнопки для Telegram, VK, WhatsApp
- **Поиск по страницам** с фильтрацией по категориям
- **Блоки контента** — дополнительные секции на странице
- **Адаптивный дизайн** — работает на мобильных и десктопе
- **Тёмная тема** — поддержка dark mode Bootstrap 5

### Админ-панель
- Управление страницами с визуальным предпросмотром
- Управление категориями
- Настройки сайта (название, описание, контакты, соцсети)
- Статистика просмотров
- Быстрый доступ к редактированию

## 📋 Требование

- Python 3.11+
- PostgreSQL 14+ (или SQLite для dev)
- Django 5.0+

## 🛠 Установка

### 1. Клонировать проект
```bash
cd DynamicPages
```

### 2. Создать виртуальное окружение
```bash
python -m venv venv
venv\Scripts\activate          # Windows
# venv/bin/activate            # Linux/Mac
```

### 3. Установить зависимости
```bash
pip install -r requirements.txt
```

### 4. Настроить окружение
```bash
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
```

Открыть `.env` и настроить:

```ini
DEBUG=False
SECRET_KEY=ваш-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/dynamicpages_db
ALLOWED_HOSTS=example.com,www.example.com
```

### 5. Сгенерировать SECRET_KEY
```bash
python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Вставить результат в `.env`

### 6. PostgreSQL (если используется)
```sql
CREATE USER dynamicpages WITH PASSWORD 'your_password';
CREATE DATABASE dynamicpages_db OWNER dynamicpages;
GRANT ALL PRIVILEGES ON DATABASE dynamicpages_db TO dynamicpages;
```

### 7. Применить миграции
```bash
python manage.py migrate
```

### 8. Создать суперпользователя
```bash
python manage.py createsuperuser
```

### 9. Запустить
```bash
python manage.py runserver
```

Открыть: http://127.0.0.1:8000

## 📁 Структура проекта

```
DynamicPages/
├── .env.example              # Пример .env
├── .gitignore               # Исключения Git
├── manage.py                # Django CLI
├── requirements.txt         # Зависимости
├── README.md                # Документация
├── dynamicpages/            # Конфигурация проекта
│   ├── __init__.py
│   ├── settings.py          # Настройки (DB, CKEditor, ...)
│   ├── urls.py              # Корневые URL-маршруты
│   ├── wsgi.py             # WSGI-конфиг
│   └── asgi.py             # ASGI-конфиг
├── pages/                   # Приложение управления страницами
│   ├── __init__.py
│   ├── admin.py             # Админ-панель
│   ├── apps.py
│   ├── forms.py             # Формы
│   ├── migrations/          # Миграции БД
│   ├── models.py            # Модели (Page, Category, ...)
│   ├── signals.py           # Сигналы Django
│   ├── urls.py              # URL-маршруты приложения
│   └── views.py             # Вьюхи (CRUD, SEO, ...)
├── templates/               # Шаблоны
│   ├── base.html            # Базовый шаблон
│   ├── home.html            # Главная страница
│   └── pages/
│       ├── list.html        # Список страниц
│       ├── detail.html      # Детальная страница
│       ├── category_detail.html  # Категория
│       ├── form.html        # Формы (create/edit)
│       └── confirm_delete.html  # Подтверждение удаления
├── static/                  # Статические файлы
│   ├── css/
│   │   └── style.css        # Пользовательские стили
│   └── js/                  # JavaScript
├── media/                   # Загруженные файлы
│   ├── pages/               # Featured images
│   └── blocks/              # Images for PageBlock
└── db.sqlite3               # SQLite для dev (опционально)
```

## 🔧 URL-маршруты

| Путь | Описание |
|------|----------|
| `/` | Главная страница |
| `/pages/` | Все страницы (с поиском и пагинацией) |
| `/page/<slug>/` | Детальная страница |
| `/category/<slug>/` | Список страниц категории |
| `/admin/pages/create/` | Создать страницу |
| `/admin/pages/<slug>/edit/` | Редактировать страницу |
| `/admin/categories/create/` | Создать категорию |
| `/api/health/` | Проверка работоспособности API |

## 🗄 Модели

### Page
- title, slug, content (RichText)
- excerpt, meta tags
- featured_image
- status (Published/Draft)
- category (ForeignKey)
- view_count, is_featured
- author, published_at

### PageCategory
- title, slug, description
- is_active, pages count

### PageBlock
- title, content (RichText), image
- ordering

### SiteSetting
- key (site_title, site_email, ...)
- value (textarea)

## 🔐 Безопасность

- CSRF защита (встроена в Django)
- Регулярные обновления зависимостей
- .env с секретами в .gitignore
- Проверка статуса публикации для публичных страниц

## 📊 Статистика (пример)

```python
# В Shell Django
>>> from pages.models import Page
>>> Page.objects.count()                     # Всего страниц
>>> Page.objects.filter(status='published').count()  # Опубликованных
>>> Page.objects.filter(view_count__gt=100).count()  # Популярные (>100 просм)
```

## 🎨 Кастомизация

### Цвета
В `settings.py` или `static/css/style.css`:
```css
--primary-color: #0d6efd;
--primary-hover: #0b5ed7;
```

### Мета-теги по умолчанию
В `settings.py`:
```python
DEFAULT_SITE_TITLE = 'MySite'
DEFAULT_SITE_DESCRIPTION = 'Описание'
DEFAULT_LANG = 'ru-ru'
```

### CKEditor
В `settings.py`:
```python
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Full',
        'height': 400,
    },
}
```

## 🐳 Docker (опционально)

### docker-compose.yml
```yaml
version: '3.8'
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dynamicpages_db
      POSTGRES_USER: dynamicpages
      POSTGRES_PASSWORD: your_password
    volumes:
      - pgdata:/var/lib/postgresql/data

  web:
    build: .
    command: >
      gunicorn dynamicpages.wsgi:application
      --bind 0.0.0.0:8000
      --workers 4
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db

volumes:
  pgdata:
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

## 📝 Разработка

```bash
# Локальная разработка с SQLite
python manage.py runserver 0.0.0.0:8000

# Миграции
python manage.py makemigrations
python manage.py migrate

# Суперпользователь
python manage.py createsuperuser

# Статика
python manage.py collectstatic
```

## 🔄 Миграция на PostgreSQL

1. Установить `psycopg2-binary`
2. Создать БД и пользователя
3. Обновить `.env`:
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ```
4. Выполнить миграции:
   ```bash
   python manage.py migrate
   ```

## 🛡️ Production Checklist

- [ ] `DEBUG=False`
- [ ] `SECRET_KEY` установлен (не дефолтный)
- [ ] `ALLOWED_HOSTS` настроен
- [ ] `DATABASE_URL` указывает на PostgreSQL
- [ ] `gunicorn` установлен
- [ ] `whitenoise` установлен
- [ ] SSL сертификат настроен
- [ ] Static/media файлы обслуживаются через CDN или отдельный веб-сервер
- [ ] Бэкапы БД настроены

## 📄 Лицензия

MIT

## 👤 Автор

Динамический сайт на Django 5.0 + PostgreSQL с CKEditor.
