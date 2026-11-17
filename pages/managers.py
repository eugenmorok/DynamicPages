"""
Оптимизированные QuerySet менеджеры для моделей.
"""
from django.db import models
from django.conf import settings


class PublishedPageManager(models.Manager):
    """Менеджер только для опубликованных страниц."""
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
