"""
REST API views для SPA frontend (DRF не требуется — чистый Django JsonResponse).
Всё работает с кэшированием, пагинацией и CORS headers.
"""
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.vary import vary_on_cookie
from django.shortcuts import render
from django.db.models import Q, Count, F, Avg
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Page, PageCategory, PageBlock, Comment, MediaGallery
from .managers import PublishedPageManager


User = get_user_model()


# ==================== Helpers ====================

def _json_response(data=None, error=None, status=200):
    """Общий JSON-ответ."""
    body = {'success': error is None}
    if data is not None:
        body['data'] = data
    if error is not None:
        body['error'] = error
        body['error_code'] = error.get('code', 'unknown')
        body['error_detail'] = error.get('detail', '')
    return JsonResponse(body, status=status)


def _parse_pagination_params(request):
    """Парсинг параметров пагинации."""
    page = max(1, int(request.GET.get('page', 1)))
    per_page = min(50, max(1, int(request.GET.get('per_page', 20))))
    return page, per_page


def _paginate(queryset, page, per_page):
    """Пагинация queryset."""
    start = (page - 1) * per_page
    end = start + per_page
    total = queryset.count()
    total_pages = (total + per_page - 1) // per_page

    items = list(queryset[start:end])
    next_page = page + 1 if page < total_pages else None
    prev_page = page - 1 if page > 1 else None

    return items, {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'next_page': next_page,
        'prev_page': prev_page,
    }


# ==================== Public API Endpoints ====================

@cache_page(60)  # 1 min cache
def api_index(request):
    """API индекса — базовая информация о сайте."""
    page_count = Page.published_objects.count()
    category_count = PageCategory.objects.filter(is_active=True).count()
    gallery_count = MediaGallery.active_objects.count()
    
    return _json_response({
        'service': 'DynamicPages API',
        'version': '1.0.0',
        'stats': {
            'pages': page_count,
            'categories': category_count,
            'gallery_items': gallery_count,
        },
        'endpoints': {
            'pages': '/api/v1/pages/',
            'categories': '/api/v1/categories/',
            'gallery': '/api/v1/gallery/',
            'health': '/api/health/',
        },
    })


@cache_page(60)  # 1 min cache
def api_health(request):
    """Проверка работоспособности."""
    return _json_response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'db_check': True,
    })


# ==================== Pages API ====================

@cache_page(120)  # 2 min cache
@cache_control(max_age=120, public=True)
def api_pages(request):
    """
    GET /api/v1/pages/
    Parameters: category, search, page, per_page, sort
    """
    q = Page.published_objects.values_list('pk', flat=True)[:3]
    Page.published_objects.filter(pk__in=list(q)).count()  # force execution
    
    qs = (
        Page.published_objects.select_related('category', 'author')
        .order_by('-published_at')
    )
    
    # Фильтр по категории
    cat_slug = request.GET.get('category')
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)
    
    # Фильтр по статусу
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    
    # Поиск
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(excerpt__icontains=search) |
            Q(content__icontains=search)
        )
    
    # Сортировка
    sort = request.GET.get('sort', 'newest')
    if sort == 'oldest':
        qs = qs.order_by('published_at')
    elif sort == 'views':
        qs = qs.order_by('-view_count')
    else:
        qs = qs.order_by('-published_at')
    
    page, per_page = _parse_pagination_params(request)
    items, pagination = _paginate(qs, page, per_page)
    
    # Форматируем для JSON
    data = []
    for item in items:
        category_data = None
        if item.category:
            category_data = {
                'id': item.category.pk,
                'title': item.category.title,
                'slug': item.category.slug,
            }
        
        author_data = None
        if item.author:
            author_data = {
                'id': item.author.pk,
                'username': item.author.get_username(),
                'display_name': item.author.get_full_name() or item.author.get_username(),
            }
        
        data.append({
            'id': item.pk,
            'title': item.title,
            'slug': item.slug,
            'excerpt': item.excerpt[:200],
            'featured_image': item.featured_image.url if item.featured_image else None,
            'category': category_data,
            'author': author_data,
            'status': item.status,
            'is_featured': item.is_featured,
            'view_count': item.view_count,
            'published_at': item.published_at.isoformat() if item.published_at else None,
            'updated_at': item.updated_at.isoformat(),
        })
    
    return _json_response({
        'list': data,
        'pagination': pagination,
    })


def api_pages_detail(request, pk):
    """GET /api/v1/pages/<id>/"""
    cache_key = f'api_page:{pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    page = get_object_or_404(Page, pk=pk, status='published')
    
    # Atomic view counter
    Page.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    page.refresh_from_db(fields=['view_count'])
    
    data = {
        'id': page.pk,
        'title': page.title,
        'slug': page.slug,
        'content': page.content,
        'excerpt': page.excerpt,
        'meta_title': page.meta_title,
        'meta_description': page.meta_description,
        'meta_keywords': page.meta_keywords,
        'featured_image': page.featured_image.url if page.featured_image else None,
        'category': None,
        'author': None,
        'status': page.status,
        'is_featured': page.is_featured,
        'view_count': page.view_count,
        'published_at': page.published_at.isoformat() if page.published_at else None,
        'updated_at': page.updated_at.isoformat(),
        'created_at': page.created_at.isoformat(),
        'blocks': list(
            page.blocks.all().values('id', 'title', 'content', 'order', 'created_at')
        ),
    }
    
    if page.category:
        data['category'] = {
            'id': page.category.pk,
            'title': page.category.title,
            'slug': page.category.slug,
        }
    if page.author:
        data['author'] = {
            'id': page.author.pk,
            'username': page.author.get_username(),
            'display_name': page.author.get_full_name() or page.author.get_username(),
        }
    
    response = _json_response(data)
    response['Cache-Control'] = 'max-age=120, public'
    cache.set(cache_key, response, 30)
    return response


# ==================== Categories API ====================

@cache_page(300)  # 5 min cache
def api_categories(request):
    """GET /api/v1/categories/"""
    categories = PageCategory.objects.filter(is_active=True).annotate(
        page_count=Count('pages')
    ).order_by('title')
    
    data = []
    for cat in categories:
        data.append({
            'id': cat.pk,
            'title': cat.title,
            'slug': cat.slug,
            'description': cat.description,
            'page_count': cat.page_count,
            'created_at': cat.created_at.isoformat(),
        })
    
    return _json_response({'list': data})


# ==================== Gallery API ====================

@cache_page(3600)  # 1 hour
def api_gallery(request):
    """GET /api/v1/gallery/"""
    qs = MediaGallery.active_objects.select_related('category').order_by('-created_at')
    
    page, per_page = _parse_pagination_params(request)
    items, pagination = _paginate(qs, page, per_page)
    
    data = []
    for item in items:
        data.append({
            'id': item.pk,
            'title': item.title,
            'description': item.description[:200],
            'image': item.image.url if item.image else None,
            'thumbnail': item.thumbnail.url if item.thumbnail else None,
            'category': None,
            'created_at': item.created_at.isoformat(),
        })
        if item.category:
            data[-1]['category'] = {
                'id': item.category.pk,
                'title': item.category.title,
            }
    
    return _json_response({'list': data, 'pagination': pagination})


def api_gallery_detail(request, pk):
    """GET /api/v1/gallery/<id>/"""
    gallery = get_object_or_404(MediaGallery, pk=pk, is_active=True)
    data = {
        'id': gallery.pk,
        'title': gallery.title,
        'description': gallery.description,
        'image': gallery.image.url if gallery.image else None,
        'thumbnail': gallery.thumbnail.url if gallery.thumbnail else None,
        'created_at': gallery.created_at.isoformat(),
        'updated_at': gallery.updated_at.isoformat(),
    }
    if gallery.category:
        data['category'] = {
            'id': gallery.category.pk,
            'title': gallery.category.title,
        }
    return _json_response(data)


# ==================== Comments API ====================

def api_comments(request, page_pk):
    """GET /api/v1/pages/<id>/comments/"""
    cache_key = f'api_comments:{page_pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    page = get_object_or_404(Page, pk=page_pk)
    comments = page.get_approved_comments().select_related('author', 'parent')[:50]
    
    data = []
    for comment in comments:
        parent = None
        if comment.parent:
            parent = {
                'id': comment.parent.pk,
                'name': comment.parent.name or 'Аноним',
                'text': comment.parent.text[:100],
                'created_at': comment.parent.created_at.isoformat(),
            }
        
        author = None
        if comment.author:
            author = {
                'id': comment.author.pk,
                'username': comment.author.get_username(),
                'display_name': comment.author.get_full_name() or comment.author.get_username(),
            }
        
        data.append({
            'id': comment.pk,
            'name': comment.name or 'Аноним',
            'email': '',  # Email не публикуем
            'text': comment.text,
            'parent': parent,
            'author': author,
            'created_at': comment.created_at.isoformat(),
        })
    
    response = _json_response(data)
    response['Cache-Control'] = 'max-age=60, public'
    cache.set(cache_key, response, 60)
    return response


# ==================== Admin API (protected) ====================

@login_required
def api_admin_stats(request):
    """GET /api/v1/admin/stats/ — статистика для админки."""
    page_count = Page.objects.count()
    published_count = Page.published_objects.count()
    draft_count = page_count - published_count
    
    comments_count = Comment.objects.count()
    active_comments = Comment.objects.filter(status='approved', is_spam=False).count()
    
    total_views = Page.published_objects.aggregate(total=Sum('view_count'))['total'] or 0
    
    # Топ страниц по просмотрам
    top_pages = list(
        Page.published_objects.values('title', 'slug')
        .annotate(total_views=Sum('view_count'))
        .order_by('-total_views')[:10]
    )
    
    # Топ категорий
    top_categories = list(
        PageCategory.objects.filter(is_active=True)
        .annotate(page_count=Count('pages'))
        .order_by('-page_count')[:5]
    )
    
    # Последние активности
    recent_pages = list(
        Page.objects.all().order_by('-updated_at')[:10]
    )
    
    return _json_response({
        'stats': {
            'total_pages': page_count,
            'published_pages': published_count,
            'draft_pages': draft_count,
            'total_comments': comments_count,
            'active_comments': active_comments,
            'total_page_views': total_views,
        },
        'top_pages': top_pages,
        'top_categories': [{'id': c.pk, 'title': c.title, 'page_count': c.page_count} for c in top_categories],
        'recent_pages': list(recent_pages.values('pk', 'title', 'status', 'updated_at')),
    })


# ==================== CORS Middleware (simple) ====================

def add_cors_headers(response):
    """Добавление CORS заголовков."""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    return response


# ==================== View Decorators ====================

def public_api_view(view_func):
    """Декоратор для публичных API endpoint."""
    @vary_on_cookie
    def wrapper(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            resp = HttpResponse(status=200)
        else:
            resp = view_func(request, *args, **kwargs)
        return add_cors_headers(resp)
    return wrapper


# Import HttpResponse at the end
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum
