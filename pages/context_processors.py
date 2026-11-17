"""
Контекстный процессор для общих переменных шаблонов.
Всегда доступны: site_title, site_description, categories, last_year.
"""
from .models import PageCategory, SiteSetting
from django.db.models import Count


def common_settings(request):
    return {
        'site_title': SiteSetting.get_value('site_title', 'DynamicPages'),
        'site_description': SiteSetting.get_value('site_description', ''),
        'last_year': '2026',
        'categories': PageCategory.objects.filter(
            is_active=True
        ).annotate(page_count=Count('pages')).order_by('title'),
    }
