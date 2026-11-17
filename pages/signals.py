"""
Сигналы для автоматизации задач.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Page


@receiver(post_save, sender=Page)
def page_saved(sender, instance, **kwargs):
    """Очистить кеш при обновлении страницы."""
    from django.utils.text import slugify
    page_slug = instance.slug or slugify(instance.title)
    cache.delete(f'page_detail:{page_slug}')
    cache.delete(f'related:{page_slug}')
    cache.delete(f'comments:{page_slug}')
    cache.delete('featured_pages')


@receiver(post_delete, sender=Page)
def page_deleted(sender, instance, **kwargs):
    """Очистить кеш при удалении страницы."""
    cache.delete(f'page_list_published')
    cache.delete('featured_pages')
