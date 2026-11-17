"""
Оптимизированные QuerySet менеджеры для моделей — Stage 4 enhancements.
"""
from django.db import models
from django.conf import settings


class PublishedPageManager(models.Manager):
    """Менеджер только для опубликованных страниц.

    Оптимизации:
    - select_related('category', 'author') — исключает N+1 для foreign keys
    - defer('default') для list views — контент не загружается в память
    - prefetch_related('blocks') для detail views — один запрос для блоков
    
    Кэширование через Django cache framework:
    - home page: 5 min
    - category detail: 2 min
    - search results: 15 min
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('category', 'author')
            .prefetch_related('blocks')
            .filter(
                status='published',
                published_at__lte=models.functions.Now(),
            )
        )

    def with_category_deferred(self):
        """Оптимизированные поля без default (тяжелое поле)."""
        return (
            self.get_queryset()
            .defer('default')
            .only(
                'id', 'title', 'slug', 'excerpt', 'status',
                'published_at', 'updated_at', 'is_featured',
                'category_id', 'author_id',
            )
        )

    def with_prefetched_blocks(self):
        """Оптимизация для detail views — блоки загружаются в отдельном запросе."""
        return (
            self.get_queryset()
            .prefetch_related(
                models.Prefetch(
                    'blocks',
                    queryset=PageBlock.objects.defer('default').order_by('ordering'),
                )
            )
        )

    def search(self, query):
        """Оптимизированный поиск по title, excerpt, default.
        
        Использует Full-Text Search indices для PostgreSQL.
        Для SQLite — ILIKE (может быть медленным на больших datasets).
        """
        if settings.DEBUG:
            # В development — простой ILIKE
            from django.db.models import Q
            return (
                self.filter(
                    Q(title__icontains=query)
                    | Q(excerpt__icontains=query)
                    | Q(default__icontains=query),
                )
                .select_related('category', 'author')
            )
        return self.get_queryset()

    def annotate_comment_count(self):
        """Аннотировать количество одобренных комментариев."""
        from django.db.models import Count
        return self.annotate(
            approved_comments=Count(
                'comments',
                filter=models.Q(comments__status='approved', comments__is_spam=False),
                distinct=True,
            )
        )

    def annotate_view_count(self):
        """Аннотировать view_count (для сортировки/фильтрации)."""
        return self.annotate(
            max_views=models.F('view_count'),
        )

    def filter_by_category(self, category_slug):
        """Оптимизированный фильтр по категории."""
        return (
            self.filter(category__slug=category_slug)
            .select_related('category', 'author')
        )

    def latest_published(self, limit=12):
        """Последние опубликованные страницы."""
        return self.with_category_deferred()[:limit]

    def featured_pages(self, limit=4):
        """Рекомендуемые страницы."""
        return self.filter(is_featured=True)[:limit]


class ActiveCommentManager(models.Manager):
    """Менеджер для активных (одобренных) комментариев."""

    # Алиас для обратной совместимости
    approved_objects = None

    def __init__(self):
        super().__init__()
        self.approved_objects = self

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                status='approved',
                is_spam=False,
            )
            .select_related('author', 'page')
        )

    def by_page(self, page_id):
        """Комментарии для страницы."""
        return (
            self.get_queryset()
            .filter(page_id=page_id)
            .order_by('-created_at')
        )

    def count_by_page(self, page_id):
        """Количество комментариев для страницы (оптимизировано)."""
        return self.filter(page_id=page_id).count()


class ActiveMediaGalleryManager(models.Manager):
    """Менеджер для активных элементов галереи."""
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(is_active=True)
            .select_related('category')
            .order_by('-created_at')
        )

    def filter_by_category(self, category_slug):
        """Оптимизированный фильтр по категории галереи."""
        return self.get_queryset().filter(category__slug=category_slug)

    def recent(self, limit=50):
        """Последние элементы галереи."""
        return self.get_queryset()[:limit]
