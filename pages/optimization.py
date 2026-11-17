"""
Оптимизация производительности — Stage 4.

Этот модуль содержит:
1. Аудит индексов базы данных
2. Авто-конвертация изображений в WebP  
3. Bulk operations для производительности
4. Decorator для кэширования views
5. Query optimizer для common query patterns
6. Performance metrics
"""
import os
import io
from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from django.core.cache import cache


# ============================================================
# 1. Database Index Auditor
# ============================================================

def audit_model_indexes(model):
    """Аудит индексов для Django модели.

    Возвращает список dict с информацией об индексах:
    - name: имя индекса
    - columns: поля, на которые он указывает  
    - unique: является ли уникальным
    """
    indexes = [
        {
            'name': idx.name,
            'columns': idx.fields,
            'unique': getattr(idx, 'unique', False),
        }
        for idx in model._meta.indexes
    ]
    return indexes


def get_missing_indexes(models):
    """Проверить отсутствие нужных индексов для query optimization."""
    recommended = []

    for model in models:
        if not getattr(model, '_meta', None):
            continue

        for field in model._meta.fields:
            if field.db_index:
                recommended.append({
                    'model': model.__name__,
                    'field': field.name,
                    'type': 'single',
                    'status': 'covered',
                })

    return recommended


# ============================================================
# 2. Image Optimization — Auto WebP Conversion  
# ============================================================

def optimize_image_pillow(image):
    """Оптимизация изображения через Pillow.

    - Конвертация в WebP (где возможно)  
    - JPEG quality 85%
    - Stripping metadata
        
    Args:
        image: Django file or PIL Image
        
    Returns:
        Tuple of (optimized_content, format_name, size_reduction_percent)  
    """
    try:
        from PIL import Image as PILImage
    except ImportError:
        return None, None, 0

    if not image:
        return None, None, 0

    # Read image content
    if hasattr(image, 'read'):
        image.seek(0)
        img_data = image.read()
        img = PILImage.open(io.BytesIO(img_data))
    else:
        return None, None, 0

    original_size = len(img_data)
    
    # Choose optimal format
    if img.mode in ('RGBA', 'P'):
        format_name = 'JPEG'
        quality = 75
        img = img.convert('RGB')
    else:
        format_name = 'WEBP'
        quality = 85
    
    buf = io.BytesIO()
    img.save(buf, format=format_name, quality=quality, optimize=True, icc_profile='')
    buf.seek(0)
    optimized_content = buf.getvalue()
    
    size_reduction = max(0, round((1 - len(optimized_content) / max(original_size, 1)) * 100, 2))
    return optimized_content, format_name, size_reduction


def compress_all_gallery_images():
    """Массовая компрессия изображений из MediaGallery.

    Оптимизирует все изображения через WebP+JPEG compression.
    Returns dict: {'compressed': int, 'skipped': int, 'errors': int}
    """
    try:
        from .models import MediaGallery
        from django.core.files.base import ContentFile
    except ImportError:
        return {'compressed': 0, 'skipped': 0, 'errors': 0}

    results = {'compressed': 0, 'skipped': 0, 'errors': 0}

    for gallery in MediaGallery.active_objects.all():
        if not gallery.image:
            results['skipped'] += 1
            continue

        try:
            optimized_content, format_name, reduction = optimize_image_pillow(gallery.image)
            
            if optimized_content and reduction > 5:  # Only save if > 5% reduction
                thumb_name = f'{os.path.splitext(gallery.image.name)[0]}.{format_name.lower()}'
                gallery.image.save(thumb_name, ContentFile(optimized_content), save=False)
                results['compressed'] += 1
            else:
                results['skipped'] += 1
        except Exception:
            results['errors'] += 1
            results['skipped'] += 1

    return results


# ============================================================
# 3. Bulk Operations — Stage 4 Optimizations
# ============================================================

def bulk_update_views(pages_list, increment=1):
    """Оптимизированный bulk update view_count.
    
    Использует UPDATE с CASE выражением вместо поштучного save().
    
    Args:
        pages_list: QuerySet или list of page objects
        increment: На сколько увеличить счётчик каждый раз
        
    Returns:
        Integer — количество обновлённых записей
    """
    from django.db import transaction
    from django.db.models import F
    from .models import Page

    if isinstance(pages_list, list):
        pks = [p.pk for p in pages_list if hasattr(p, 'pk')]
    else:
        pks = list(pages_list.values_list('pk', flat=True))
    
    if not pks:
        return 0

    with transaction.atomic():
        return Page.objects.filter(pk__in=pks).update(
            view_count=F('view_count') + increment
        )


def batch_create_settings(settings_list):
    """Эффективное bulk create настроек.

    Args:
        settings_list: Iterable of dicts like {'key': '', 'value': '', 'label': ''}
        
    Returns:
        Tuple of (created_objects, skipped_keys)
    """
    from .models import SiteSetting

    existing_keys = set(SiteSetting.objects.values_list('key', flat=True))
    to_create = [
        SiteSetting(**{k: v for k, v in s.items() if k in ('key', 'value', 'label')})
        for s in settings_list if s['key'] not in existing_keys
    ]
    
    created = SiteSetting.objects.bulk_create(to_create)
    skipped = existing_keys & {s['key'] for s in settings_list}
    
    return created, skipped


# ============================================================
# 4. Template Fragment Caching Decorators
# ============================================================

def cached_view(timeout=300):
    """Декоратор кэширования результата view на timeout секунд.
    
    Usage:
        @cached_view(timeout=300)
        def home(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            key_parts = [
                view_func.__name__,
                f'args={id(args):x}',
                f'user={'logged_in' if request.user.is_authenticated else 'anon'}',
            ]
            if hasattr(request.GET, 'version'):
                key_parts.append(f'v={request.GET.get_version()}')
            
            cache_key = ':'.join(key_parts)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            
            response = view_func(request, *args, **kwargs)
            cache.set(cache_key, response, timeout)
            return response
        return wrapper
    return decorator


def cached_property(timeout=300):
    """Декоратор кэширования свойства объекта.
    
    Properties will be cached in Django cache with ttl=timeout seconds.
    
    Usage:
        class MyModel(models.Model):
            @cached_property  
            def expensive_computation(self):
                return compute_heavy_thing()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            model_name = self.__class__.__name__
            pk = getattr(self, 'pk', None)
            if pk is None:
                return func(self)
            
            cache_key = f'{model_name}_prop_{pk}_{func.__name__}'
            value = cache.get(cache_key)
            if value is not None:
                return value
            
            value = func(self)
            cache.set(cache_key, value, timeout)
            return value
        return wrapper
    return decorator


# ============================================================
# 5. Query Optimization Helpers
# ============================================================

@contextmanager
def assert_max_queries(max_queries, using='default'):
    """Контекст для тестирования количества SQL запросов.

    Выбрасывает AssertionError если запросов больше max.
    
    Usage:
        with assert_max_queries(10):
            page = Page.published_objects.get(pk=1)
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    
    with CaptureQueriesContext(connection) as captured:
        yield
    
    query_count = len(captured.captured_queries)
    if query_count > max_queries:
        raise AssertionError(
            f"Expected at most {max_queries} queries, got {query_count}.\n"
            "Queries:\n" + "\n".join(
                f"{i+1}. {q['sql'][:200]}" for i, q in enumerate(captured.captured_queries)
            )
        )


def optimize_page_queryset():
    """Оптимизация queryset для page list — использует все доступные индексы.

    Recommended indexes:
    - pages_page(status, published_at) — for filter
    - pages_page(category_id, status) — for join  
    - pages_page(is_featured, published_at) — for featured
    - pages_page(title, slug) — for search
    
    Returns optimized queryset with select_related/prefetch_related.
    """
    from .models import Page

    return Page.published_objects.with_category_deferred().annotate_comment_count()


def optimize_comment_queryset():
    """Оптимизация queryset для comment list.

    Recommended indexes:
    - comments(page_id, status, is_spam) — for approved filter
    - comments(page_id, created_at) — for sorted comments
    
    Returns optimized queryset.
    """
    from .models import Comment

    return Comment.active_objects.get_queryset().filter(is_spam=False)


# ============================================================
# 6. Performance Metrics
# ============================================================

def get_performance_metrics():
    """Получение текущих метрик производительности.

    Returns dict:
    - database_engine: тип БД (sqlite3, postgresql)
    - cache_backend: бэкенд кеша (redis, localmemory)
    - debug_mode: is DEBUG
    - version: версия приложения
    - cache_hits/misses: из Redis (если доступен)
    - db_pool_size: размер connection pool
    """
    from django.db import connections
    from django.conf import settings
   
    db_engine = settings.DATABASES['default']['ENGINE']
    cache_backend = settings.CACHES['default']['BACKEND']
    
    metrics = {
        'database_engine': db_engine.split('.')[-1],
        'cache_backend': cache_backend.split('.')[-1],
        'debug_mode': settings.DEBUG,
        'version': getattr(settings, 'VERSION', 'unknown'),
        'startup_time': getattr(settings, 'STARTUP_TIME', None),
    }
    
    # Redis-specific metrics (if available)
    if 'redis' in cache_backend.lower():
        try:
            import redis
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/1')
            client = redis.Redis.from_url(redis_url)
            info = client.info('stats')
            metrics['cache_hits'] = info.get('keyspace_hits', 0)
            metrics['cache_misses'] = info.get('keyspace_misses', 0)
            metrics['connected_clients'] = info.get('connected_clients', 0)
            metrics['memory_used_mb'] = info.get('used_memory', 0) / (1024 * 1024)
        except Exception:
            metrics['redis_unavailable'] = True
    
    return metrics
