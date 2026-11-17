"""
Оптимизированная генерация sitemap.
Использует iterator() для минимизации потребления памяти.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Page, PageCategory, MediaGallery


class StaticSitemap(Sitemap):
    """Статические URL сайта."""

    def items(self):
        return ['home', 'pages:page_list', 'pages:category_list',
                'pages:gallery_list']

    def priority(self, obj):
        return 0.9 if obj == 'home' else 0.8

    def changefreq(self, obj):
        return 'monthly' if obj != 'home' else 'weekly'


class PageSitemap(Sitemap):
    """Sitemap для опубликованных страниц."""
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        # Используем iterator() для экономии памяти на больших сайтах
        return Page.published_objects.values_list('updated_at', 'slug', 'priority').iterator(chunk_size=500)

    def lastmod(self, item):
        return item[0]

    def location(self, item):
        return f'/page/{item[1]}/'

    def priority(self, item):
        return item[2] if len(item) > 2 else 0.7


class CategorySitemap(Sitemap):
    """Sitemap для категорий."""
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return PageCategory.objects.filter(is_active=True).values_list('updated_at', 'slug').iterator(chunk_size=100)

    def lastmod(self, item):
        return item[0]

    def location(self, item):
        return f'/category/{item[1]}/'


class GallerySitemap(Sitemap):
    """Sitemap для медиогалереи."""
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return MediaGallery.active_objects.values_list('updated_at', 'pk').iterator(chunk_size=500)

    def lastmod(self, item):
        return item[0]

    def location(self, item):
        return f'/gallery/{item[1]}/'


def get_sitemaps():
    """Возвращает словарь sitemap'ов для настройки в urls.py."""
    return {
        'static': StaticSitemap,
        'pages': PageSitemap,
        'categories': CategorySitemap,
        'gallery': GallerySitemap,
    }
