# ============================================================
# Этап 5: Оптимизация — Мониторинг и APM
# ============================================================

import os
import time
import logging
from functools import wraps
from django.db import connection
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('performance')

# ============================================================
# Monitoring middleware — timing each request
# ============================================================

class PerformanceMiddleware:
    """Мониторинг производительности: timing, slow queries, cache hits."""
    
    # Threshold for slow queries (ms)
    SLOW_QUERY_THRESHOLD = 100  # ms
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request._start_time = time.time()
        
        # Add request start tracking
        request._query_count = 0
        request._query_time = 0.0
        try:
            from django.db import connection
            request._query_count = len(connection.queries)
            request._query_time = sum(q['time'] for q in connection.queries)
        except Exception:
            pass
        
        response = self.get_response(request)
        
        # Calculate response time
        elapsed = (time.time() - getattr(request, '_start_time', time.time())) * 1000
        response['X-Response-Time'] = f'{elapsed:.2f}ms'
        
        # Log slow requests (>500ms)
        if elapsed > 500:
            logger.warning(
                'Slow request: %s %s (%.2f ms)',
                request.method,
                request.build_absolute_uri(),
                elapsed,
            )
            response['X-Slow-Request'] = 'true'
        
        # Log query count and time
        try:
            q_count = len(connection.queries)
            q_time = sum(q['time'] for q in connection.queries)
            response['X-Queries'] = str(q_count)
            response['X-Query-Time'] = f'{q_time * 1000:.1f}ms'
            
            if q_count > 50:
                logger.warning('High query count: %d for %s', q_count, request.build_absolute_uri())
                response['X-High-Queries'] = 'true'
        except Exception:
            pass
        
        return response


class CacheMonitorMiddleware:
    """Мониторинг кэширования."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        from django.core.cache import cache
        
        # Track cache accesses before the request
        cache_before_hits = cache.get_hits if hasattr(cache, 'get_hits') else 0
        
        response = self.get_response(request)
        
        # Add cache hit ratio header
        if hasattr(cache, 'get_hits'):
            hits = cache.get_hits
            total = cache.get_total_lookups
            if total > 0:
                ratio = hits / total * 100
                response['X-Cache-Hit-Ratio'] = f'{ratio:.1f}%'
        else:
            response['X-Cache-Hit-Ratio'] = 'N/A (locmem)'
        
        return response


# ============================================================
# Query optimizer — track slow queries
# ============================================================

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.utils import CursorWrapper

_original_execute = BaseDatabaseWrapper.make_error_callable(None)


class QueryMonitor:
    """Мониторинг SQL запросов в реальном времени."""
    
    def __init__(self):
        self.slow_queries = []
        self.total_queries = 0
        self.enabled = os.environ.get('PERFORMANCE_MONITOR', '0') == '1'
    
    def check_query(self, sql, duration=None):
        """Проверка запроса на медленность."""
        if not self.enabled or not duration:
            return
        
        self.total_queries += 1
        
        if duration > QueryMonitor.SLOW_QUERY_THRESHOLD / 1000:
            import traceback
            stack = traceback.extract_stack()
            self.slow_queries.append({
                'sql': sql[:500],
                'duration_ms': round(duration * 1000, 2),
                'stack': self._get_caller(stack),
            })
    
    def _get_caller(self, stack):
        """Извлечение caller из stack trace."""
        for frame in reversed(stack):
            if 'django' in frame.filename:
                continue
            if 'pages' in frame.filename:
                return f'{frame.filename}:{frame.lineno}'
        return 'unknown'


# ============================================================
# Health check metrics — system wide
# ============================================================

def get_system_metrics():
    """Получение метрик системы."""
    from django.db import connection
    from django.core.cache import cache
    import os
    
    metrics = {
        'db': {
            'engine': connection.vendor,
            'queries_executed': len(connection.queries),
        },
        'cache': {
            'backend': connection.settings_dict.get('BACKEND', 'locmem'),
        },
        'system': {
            'debug': settings.DEBUG,
            'version': getattr(settings, 'VERSION', '1.0'),
            'uptime_start': getattr(settings, 'STARTUP_TIME', timezone.now().isoformat()),
            'total_pages': 0,
            'published_pages': 0,
        },
    }
    
    # Add app counts
    try:
        from .models import Page, PageCategory, MediaGallery, Comment
        metrics['system']['total_pages'] = Page.objects.count()
        metrics['system']['published_pages'] = Page.published_objects.count()
        metrics['system']['categories'] = PageCategory.objects.filter(is_active=True).count()
        metrics['system']['gallery_items'] = MediaGallery.objects.count()
        metrics['system']['total_comments'] = Comment.objects.count()
    except Exception:
        pass
    
    return metrics


def health_check():
    """Проверка работоспособности всех сервисов."""
    result = {
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
    }
    
    # Database check
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        result['database'] = {'status': 'ok'}
    except Exception as e:
        result['database'] = {'status': 'error', 'error': str(e)}
        result['status'] = 'degraded'
    
    # Cache check
    try:
        from django.core.cache import cache
        cache.set('health_check_test', 'ok', 1)
        val = cache.get('health_check_test')
        if val == 'ok':
            result['cache'] = {'status': 'ok'}
        else:
            result['cache'] = {'status': 'error', 'error': 'Cache set/get failed'}
            result['status'] = 'degraded'
    except Exception as e:
        result['cache'] = {'status': 'error', 'error': str(e)}
        result['status'] = 'degraded'
    
    # Filesystem check
    try:
        import os
        os.environ.get('DJANGO_SETTINGS_MODULE')
        result['filesystem'] = {'status': 'ok'}
    except Exception as e:
        result['filesystem'] = {'status': 'error', 'error': str(e)}
    
    return result
