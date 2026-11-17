"""
REST API views для SPA frontend (DRF не требуется — чистый Django JsonResponse).
Поддержка кэширования, пагинации и CORS заголовков.
"""
from django.http import (
    JsonResponse,
    HttpResponseBadRequest,
    HttpResponse,
)
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.vary import vary_on_cookie
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, F, Avg, Sum
from functools import wraps
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.utils.safestring import mark_safe
import json

from .models import (
    Page, PageCategory, PageBlock, Comment, MediaGallery, SiteSetting, Subscription,
)
from .managers import PublishedPageManager
from .monitoring import get_system_metrics, health_check
from .rate_limiting import SimpleRateLimiter

User = get_user_model()


# ============================================================
# Helpers
# ============================================================

def _json_response(data=None, error=None, status=200):
    """Return a standardised JSON response."""
    body = {'success': error is None}
    if data is not None:
        body['data'] = data
    if error is not None:
        body['error'] = error
        body['error_code'] = error.get('code', 'unknown')
        body['error_detail'] = error.get('detail', '')
    return JsonResponse(body, status=status)


def _parse_pagination_params(request):
    """Return (page, per_page) from request.GET with sane defaults."""
    page = max(1, int(request.GET.get('page', 1)))
    per_page = min(50, max(1, int(request.GET.get('per_page', 20))))
    return page, per_page


def _paginate(queryset, page, per_page):
    """Return (items, pagination_meta) for a queryset."""
    total = queryset.count()
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = list(queryset[start:end])
    return items, {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'next_page': page + 1 if page < total_pages else None,
        'prev_page': page - 1 if page > 1 else None,
    }


def _get_client_ip(request):
    """Extract client IP from request (proxy-aware)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


CORS_ALLOW_ORIGIN = (
    'https://dynamicpages-frontend.vercel.app'
    if not __import__('os').environ.get('DEBUG', '1').startswith('0')
    else '*'
)
CORS_ALLOW_HEADERS = 'Content-Type, Authorization, X-Requested-With'
CORS_ALLOW_METHODS = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'


_CORS_APPLIED = set()  # track applied views to avoid double decoration


def _add_cors(view_func):
    """Decorate a view to attach CORS headers to its response."""
    view_name = f'{view_func.__module__}.{view_func.__name__}'
    if view_name in _CORS_APPLIED:
        return view_func

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        _CORS_APPLIED.add(view_name)
        if hasattr(response, 'get'):
            response['Access-Control-Allow-Origin'] = CORS_ALLOW_ORIGIN
            response['Access-Control-Allow-Headers'] = CORS_ALLOW_HEADERS
            response['Access-Control-Allow-Methods'] = CORS_ALLOW_METHODS
        elif hasattr(response, 'headers'):  # StreamingHttpResponse / FileResponse
            response.headers['Access-Control-Allow-Origin'] = CORS_ALLOW_ORIGIN
            response.headers['Access-Control-Allow-Headers'] = CORS_ALLOW_HEADERS
            response.headers['Access-Control-Allow-Methods'] = CORS_ALLOW_METHODS
        elif callable(response):  # may be a response class
            response['Access-Control-Allow-Origin'] = CORS_ALLOW_ORIGIN
            response['Access-Control-Allow-Headers'] = CORS_ALLOW_HEADERS
            response['Access-Control-Allow-Methods'] = CORS_ALLOW_METHODS
        return response
    return wrapper


# ============================================================
# Health & Index
# ============================================================

@cache_page(60)
@_add_cors
def api_health(request):
    """GET /api/health/"""
    return _json_response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'system_metrics': get_system_metrics(),
        'db_connected': health_check().get('status') == 'Healthy',
    })


@cache_page(60)
@_add_cors
def api_index(request):
    """GET /api/ — API index / discovery."""
    return _json_response({
        'service': 'DynamicPages API',
        'version': '1.0.0',
        'stats': {
            'pages': Page.published_objects.count(),
            'categories': PageCategory.objects.filter(is_active=True).count(),
            'gallery_items': MediaGallery.active_objects.count(),
        },
        'endpoints': {
            'pages': '/api/v1/pages/',
            'categories': '/api/v1/categories/',
            'gallery': '/api/v1/gallery/',
            'comments': '/api/v1/pages/<id>/comments/',
            'admin_stats': '/api/v1/admin/stats/',
            'health': '/api/health/',
        },
    })


# ============================================================
# Pages API
# ============================================================

@cache_page(120)
@cache_control(max_age=120, public=True)
@_add_cors
def api_pages(request):
    """GET /api/v1/pages/ — paginated list with optional filters."""
    q = Page.published_objects.with_category_deferred()

    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        q = q.filter(category__slug=category_slug)

    # Text search
    search = request.GET.get('search', '').strip()
    if search:
        q = q.filter(
            Q(title__icontains=search) |
            Q(excerpt__icontains=search) |
            Q(default__icontains=search),
        )

    # Featured filter
    if request.GET.get('featured') == '1':
        q = q.filter(is_featured=True)

    # Status filter
    status = request.GET.get('status')
    if status:
        q = q.filter(status=status)

    # Sort
    sort = request.GET.get('sort', '-published_at')
    valid_sort = {
        '-published_at': '-published_at',
        'published_at': 'published_at',
        '-views': '-view_count',
        'views': 'view_count',
        '-updated_at': '-updated_at',
        'title': 'title',
    }
    q = q.order_by(valid_sort.get(sort, '-published_at'))

    page, per_page = _parse_pagination_params(request)
    items, pagination = _paginate(q, page, per_page)

    return _json_response({
        'pages': [
            {
                'id': p.pk,
                'title': p.title,
                'slug': p.slug,
                'excerpt': p.excerpt,
                'category': {'id': p.category.pk, 'title': p.category.title, 'slug': p.category.slug},
                'status': p.status,
                'view_count': p.view_count,
                'is_featured': p.is_featured,
                'block_count': p.blocks.count(),
                'published_at': p.published_at.isoformat() if p.published_at else None,
                'updated_at': p.updated_at.isoformat(),
            }
            for p in items
        ],
        'pagination': pagination,
        'filters': {
            'category': category_slug,
            'search': search,
            'featured': request.GET.get('featured'),
            'status': status,
            'sort': sort,
        },
    })


@cache_page(120)
@_add_cors
def api_page_detail(request, pk):
    """GET /api/v1/pages/<id>/ — full page detail."""
    page = get_object_or_404(Page, pk=pk, status=Page.PUBLISHED)

    # Atomic view counter
    Page.objects.filter(pk=pk).update(view_count=F('view_count') + 1)

    cached = cache.get(f'api_page:{pk}')
    if cached is not None:
        return cached

    page_obj = Page.published_objects.get(pk=pk)
    blocks_data = [
        {
            'id': b.pk,
            'title': b.title,
            'text': b.default,
            'image': b.image.url if b.image else None,
        }
        for b in page_obj.blocks.all()
    ]

    data = {
        'id': page_obj.pk,
        'title': page_obj.title,
        'slug': page_obj.slug,
        'excerpt': page_obj.excerpt,
        'content': page_obj.default,
        'category': {'id': page_obj.category.pk if page_obj.category else None, 'title': page_obj.category.title if page_obj.category else None, 'slug': page_obj.category.slug if page_obj.category else None},
        'author': page_obj.author.get_username() if page_obj.author else None,
        'status': page_obj.status,
        'view_count': page_obj.view_count,
        'is_featured': page_obj.is_featured,
        'blocks': blocks_data,
        'published_at': page_obj.published_at.isoformat() if page_obj.published_at else None,
        'updated_at': page_obj.updated_at.isoformat(),
    }

    response = _json_response(data)
    response['Cache-Control'] = 'max-age=120, public'
    cache.set(f'api_page:{pk}', response, 120)
    return response


# ============================================================
# Categories API
# ============================================================

@cache_page(300)
@_add_cors
def api_categories(request):
    """GET /api/v1/categories/"""
    cached = cache.get('api_categories')
    if cached is not None:
        return cached

    categories = list(
        PageCategory.objects.filter(is_active=True)
        .annotate(page_count=Count('pages', filter=Q(pages__status=Page.PUBLISHED)))
        .order_by('title')
    )

    data = [
        {
            'id': c.pk,
            'title': c.title,
            'slug': c.slug,
            'description': c.description,
            'page_count': c.page_count,
            'is_active': c.is_active,
        }
        for c in categories
    ]

    response = _json_response(data)
    cache.set('api_categories', response, 300)
    return response


# ============================================================
# Gallery API
# ============================================================

@cache_page(3600)
@_add_cors
def api_gallery(request):
    """GET /api/v1/gallery/ — paginated gallery."""
    q = MediaGallery.active_objects.select_related('category')

    category_slug = request.GET.get('category')
    if category_slug:
        q = q.filter(category__slug=category_slug)

    page, per_page = _parse_pagination_params(request)
    items, pagination = _paginate(q, page, per_page)

    return _json_response({
        'items': [
            {
                'id': g.pk,
                'title': g.title,
                'description': g.description,
                'thumbnail': g.image.url if g.image else None,
                'category': {'id': g.category.pk, 'title': g.category.title, 'slug': g.category.slug},
                'is_active': g.is_active,
            }
            for g in items
        ],
        'pagination': pagination,
        'filters': {'category': category_slug},
    })


# ============================================================
# Comments API
# ============================================================

@cache_page(60)
@_add_cors
def api_comments(request, page_id):
    """GET /api/v1/pages/<id>/comments/ — approved comments."""
    page = None
    try:
        page = Page.objects.get(pk=page_id, status=Page.PUBLISHED)
    except Page.DoesNotExist:
        pass

    if not page:
        return _json_response(error={'code': 'not_found', 'detail': 'Page not found'}, status=404)

    comments = list(
        Comment.objects.filter(page_id=page_id, status='approved')
        .select_related('page')
        .order_by('-created_at')
    )

    return _json_response({
        'page': {'id': page.pk, 'title': page.title},
        'comments': [
            {
                'id': c.pk,
                'name': c.name,
                'email': c.email,
                'text': c.text,
                'created_at': c.created_at.isoformat(),
                'status': c.status,
                'is_spam': c.is_spam,
            }
            for c in comments[:50]
        ],
        'total': len(comments),
    })


@csrf_exempt
def api_submit_comment(request, page_id):
    """POST /api/v1/pages/<id>/comments/ — submit a comment."""
    if request.method != 'POST':
        return _json_response(error={'code': 'method_not_allowed', 'detail': 'Only POST allowed.'}, status=405)

    try:
        page = Page.objects.get(pk=page_id, status=Page.PUBLISHED)
    except Page.DoesNotExist:
        return _json_response(error={'code': 'not_found', 'detail': 'Page not found'}, status=404)

    data = json.loads(request.body) if hasattr(request, 'body') else json.loads(request.body.read())

    name = data.get('name', '').strip()[:100]
    email = data.get('email', '').strip()[:255]
    text = data.get('text', '').strip()[:1000]

    if not name or not email or not text:
        return _json_response(error={'code': 'validation_error', 'detail': 'name, email, and text are required.'}, status=400)

    comment = Comment.objects.create(
        page=page,
        name=name,
        email=email,
        text=text,
        status='pending',
    )

    return _json_response(
        {'id': comment.pk, 'status': comment.status, 'message': 'Comment submitted for approval.'},
        status=201,
    )


# ============================================================
# Admin stats
# ============================================================

@_add_cors
@login_required
def api_admin_stats(request):
    """GET /api/v1/admin/stats/ — admin statistics (auth required)."""
    if not request.user.is_staff:
        return _json_response(error={'code': 'forbidden', 'detail': 'Admin access required.'}, status=403)
    
    from django.db.models import Count, Q
    
    total_pages = Page.objects.count()
    published_pages = Page.published_objects.count()
    draft_pages = Page.objects.filter(status=Page.DRAFT).count()
    total_comments = Comment.objects.count()
    pending_comments = Comment.objects.filter(status=Comment.PENDING).count()
    total_categories = PageCategory.objects.count()
    active_categories = PageCategory.objects.filter(is_active=True).count()
    gallery_items = MediaGallery.objects.count()
    active_gallery = MediaGallery.objects.filter(is_active=True).count()
    active_subscriptions = Subscription.objects.filter(active=True).count()
    total_views = Page.objects.aggregate(total=Sum('view_count', default=0))['total']
    
    return _json_response({
        'pages': {
            'total': total_pages,
            'published': published_pages,
            'draft': draft_pages,
            'total_views': total_views,
        },
        'comments': {
            'total': total_comments,
            'pending': pending_comments,
        },
        'categories': {
            'total': total_categories,
            'active': active_categories,
        },
        'gallery': {
            'total': gallery_items,
            'active': active_gallery,
        },
        'subscriptions': {
            'active': active_subscriptions,
        },
    })


# ============================================================
# Gallery detail
# ============================================================

@_add_cors
def api_gallery_detail(request, pk):
    """GET /api/v1/gallery/<id>/ — single gallery item."""
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum
    gallery = get_object_or_404(MediaGallery.objects, pk=pk)
    
    return _json_response({
        'id': gallery.pk,
        'title': gallery.title,
        'description': gallery.description,
        'image': gallery.image.url if gallery.image else None,
        'thumbnail': gallery.image.url.replace('/original/', '/thumb_/') if gallery.image else None,
        'category': {
            'id': gallery.category.pk,
            'title': gallery.category.title,
            'slug': gallery.category.slug,
        },
        'is_active': gallery.is_active,
        'created_at': gallery.created_at.isoformat(),
    })
