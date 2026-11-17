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
    cache.delete(f'page_{instance.pk}')
    cache.delete(f'page_list_all')
    cache.delete(f'page_list_published')
    cache.clear()  # Временно для безопасности


@receiver(post_delete, sender=Page)
def page_deleted(sender, instance, **kwargs):
    """Очистить кеш при удалении страницы."""
    cache.delete(f'page_{instance.pk}')
    cache.clear()
