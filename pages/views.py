"""
Оптимизированные вьюхи: кэширование, defer, iterator, select_related/prefetch_related.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import models, transaction
from django.db.models import Q, Count
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache

from .models import (
    Page, PageCategory, PageBlock, SiteSetting,
    Comment, Subscription, MediaGallery,
)
from .forms import PageForm, PageCategoryForm, PageBlockForm, SearchForm
from .comments import CommentForm, ReplyForm


# ==================== Cache helpers ====================

def _get_site_setting(key, default=''):
    """Оптимизированный доступ к настройкам с кэшированием."""
    cache_key = f'setting:{key}'
    value = cache.get(cache_key)
    if value is None:
        value = SiteSetting.get_value(key, default)
        cache.set(cache_key, value, 300)
    return value


def _invalidate_page(slug):
    """Инвалидация кэша страницы."""
    cache.delete(f'page_detail:{slug}')
    cache.delete(f'related:{slug}')
    cache.delete(f'comments:{slug}')


# ==================== Public Views ====================

def home(request):
    """Главная — последние опубликованные страницы + статистика (кэш 5 мин)."""
    cache_key = f'home:{id(request.GET):x}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Page.published_objects уже делает select_related/prefetch_related
    published_pages = Page.published_objects.with_category_deferred()[:12]

    categories = PageCategory.objects.filter(
        is_active=True
    ).annotate(page_count=Count('pages')).order_by('title')

    featured = cache.get('featured_pages')
    if featured is None:
        featured = Page.published_objects.filter(is_featured=True)[:4]
        cache.set('featured_pages', featured, 1800)

    context = {
        'published_pages': published_pages,
        'categories': categories,
        'featured_pages': featured,
        'site_title': _get_site_setting('site_title', 'DynamicPages'),
        'site_description': _get_site_setting('site_description', ''),
    }
    response = render(request, 'home.html', context)
    cache.set(cache_key, response, 300)
    return response


class PageListView(ListView):
    """Список опубликованных страниц (категория + поиск)."""
    model = Page
    template_name = 'pages/list.html'
    context_object_name = 'pages'
    paginate_by = 12

    def get_queryset(self):
        qs = Page.published_objects.with_category_deferred().order_by('-published_at')

        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        search_q = self.request.GET.get('q', '').strip()
        if search_q:
            qs = qs.filter(
                Q(title__icontains=search_q) |
                Q(excerpt__icontains=search_q) |
                Q(content__icontains=search_q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = self.kwargs.get('category_slug')
        if slug:
            ctx['current_category'] = get_object_or_404(PageCategory, slug=slug)
            ctx['page_title'] = 'Страницы раздела: ' + ctx['current_category'].title
        else:
            ctx['page_title'] = 'Все страницы'
        ctx['search_form'] = SearchForm(self.request.GET)
        return ctx


def page_detail(request, slug):
    """Детальная страница (кэш 10 мин)."""
    cache_key = f'page_detail:{slug}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    page = get_object_or_404(
        Page, slug=slug, status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    )

    # Atomic F-expression для просммотров
    Page.objects.filter(pk=page.pk).update(
        view_count=models.F('view_count') + 1,
    )
    page.refresh_from_db(fields=['view_count'])

    # Оптимизированные комментарии (select_related)
    page_comments = page.get_approved_comments()[:10]

    # Похожие страницы (кэш 30 мин)
    related = cache.get(f'related:{slug}')
    if related is None:
        q = Page.published_objects.with_category_deferred().exclude(pk=page.pk)
        if page.category:
            q = q.filter(category=page.category)
        related = q.order_by('-published_at')[:4]
        cache.set(f'related:{slug}', related, 1800)

    blocks = PageBlock.objects.filter(page=page).defer('content')[:5]
    meta_title = page.meta_title or page.title
    meta_desc = page.meta_description or page.excerpt or ''

    context = {
        'page': page,
        'related_pages': related,
        'blocks': blocks,
        'page_comments': page_comments,
        'meta_title': meta_title,
        'meta_description': meta_desc,
    }
    response = render(request, 'pages/detail.html', context)
    cache.set(cache_key, response, 600)
    return response


def category_detail(request, slug):
    """Детальная страница категории (кэш 5 мин)."""
    cache_key = f'category_detail:{slug}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    category = get_object_or_404(PageCategory, slug=slug, is_active=True)
    pages = Page.published_objects.with_category_deferred().filter(
        category=category
    ).order_by('-published_at')[:20]

    context = {'category': category, 'pages': pages}
    response = render(request, 'pages/category_detail.html', context)
    cache.set(cache_key, response, 300)
    return response


# ==================== Admin Views ====================

class PageCreateView(LoginRequiredMixin, CreateView):
    model = Page
    form_class = PageForm
    template_name = 'pages/form.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, f'Страница "{form.instance.title}" создана!')
        _invalidate_page(form.instance.slug)
        return super().form_valid(form)


class PageUpdateView(LoginRequiredMixin, UpdateView):
    model = Page
    form_class = PageForm
    template_name = 'pages/form.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        messages.success(self.request, f'Страница "{form.instance.title}" обновлена!')
        _invalidate_page(self.object.slug)
        return super().form_valid(form)

    def get_success_url(self):
        _invalidate_page(self.object.slug)
        return super().get_success_url()


class PageDeleteView(LoginRequiredMixin, DeleteView):
    model = Page
    template_name = 'pages/confirm_delete.html'
    success_url = reverse_lazy('pages:home')

    def delete(self, request, *args, **kwargs):
        _invalidate_page(self.object.slug)
        messages.success(request, f'Страница "{self.object.title}" удалена!')
        return super().delete(request, *args, **kwargs)


def page_block_create(request, page_slug):
    page = get_object_or_404(Page, slug=page_slug)
    if request.method == 'POST':
        form = PageBlockForm(request.POST, request.FILES)
        if form.is_valid():
            block = form.save(commit=False)
            block.page = page
            block.save()
            _invalidate_page(page_slug)
            messages.success(request, 'Блок добавлен!')
            return redirect('pages:page_detail', page.slug)
    else:
        form = PageBlockForm()
    return render(request, 'pages/form_block.html', {'form': form, 'page': page})


def page_block_delete(request, pk):
    block = get_object_or_404(PageBlock, pk=pk)
    page_slug = block.page.slug
    if request.method == 'POST':
        block.delete()
        _invalidate_page(page_slug)
        messages.success(request, 'Блок удалён!')
        return redirect('pages:page_detail', page_slug)
    return render(request, 'pages/confirm_block_delete.html', {'block': block, 'page': block.page})


# ==================== Category Views ====================

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = PageCategory
    form_class = PageCategoryForm
    template_name = 'pages/form_category.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        messages.success(self.request, f'Категория "{form.instance.title}" создана!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = PageCategory
    form_class = PageCategoryForm
    template_name = 'pages/form_category.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        messages.success(self.request, f'Категория "{form.instance.title}" обновлена!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = PageCategory
    template_name = 'pages/confirm_delete.html'
    success_url = reverse_lazy('pages:home')

    def delete(self, request, *args, **kwargs):
        messages.success(request, f'Категория "{self.object.title}" удалена!')
        return super().delete(request, *args, **kwargs)


# ==================== Optimized Sitemap ====================

def sitemap_xml(request):
    """Оптимизированная XML-карта — использует iterator() для экономии памяти."""
    from django.conf import settings
    base_url = getattr(settings, 'SITE_URL', 'https://example.com')

    response = HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n',
        content_type='application/xml',
    )

    # Статические страницы
    for path, freq, pri in [
        ('/', 'yearly', '1.0'),
        ('/page/', 'monthly', '0.9'),
        ('/category/', 'monthly', '0.8'),
        ('/gallery/', 'weekly', '0.8'),
    ]:
        response.write(
            f'  <url><loc>{base_url}{path}</loc><changefreq>{freq}</changefreq><priority>{pri}</priority></url>\n'
        )

    # Страницы — iterator() chunk 500
    for date, slug in Page.published_objects.values_list(
        'updated_at', 'slug'
    ).iterator(chunk_size=500):
        response.write(
            f'  <url><loc>{base_url}/page/{slug}/</loc>'
            f'<lastmod>{date.strftime("%Y-%m-%d")}</lastmod></url>\n'
        )

    # Категории — iterator() chunk 100
    for date, slug in PageCategory.objects.filter(
        is_active=True
    ).values_list('updated_at', 'slug').iterator(chunk_size=100):
        response.write(
            f'  <url><loc>{base_url}/category/{slug}/</loc>'
            f'<lastmod>{date.strftime("%Y-%m-%d")}</lastmod></url>\n'
        )

    # Галерея — iterator() chunk 500
    for date, pk in MediaGallery.active_objects.values_list(
        'updated_at', 'pk'
    ).iterator(chunk_size=500):
        response.write(
            f'  <url><loc>{base_url}/gallery/{pk}/</loc>'
            f'<lastmod>{date.strftime("%Y-%m-%d")}</lastmod></url>\n'
        )

    response.write('</urlset>\n')
    return response


def robots_txt(request):
    content = 'User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap/\n'
    return HttpResponse(content, content_type='text/plain')


def health_check(request):
    """API-проверка работоспособности."""
    return JsonResponse({
        'status': 'ok',
        'pages_count': Page.objects.count(),
        'published_count': Page.published_objects.count(),
        'db_engine': __import__('django.conf').conf.settings.DATABASES['default']['ENGINE'],
    })


def page_not_found(request, exception):
    return render(request, '404.html', {
        'site_title': _get_site_setting('site_title', 'DynamicPages'),
        'site_description': _get_site_setting('site_description', ''),
    }, status=404)


def server_error(request):
    return render(request, '500.html', status=500)


# ==================== Comments ====================

def add_comment(request, slug):
    page = get_object_or_404(Page, slug=slug, status=Page.PUBLISHED)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    form = CommentForm(request.POST, page=page)
    if form.data.get('honeypot'):
        return JsonResponse({'error': 'Spam detected'}, status=400)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.page = page
        if request.user.is_authenticated:
            comment.author = request.user
            comment.name = request.user.get_full_name() or request.user.get_username()
            comment.email = request.user.email or ''
        comment.save()
        cache.delete(f'comments:{slug}')
        try:
            _send_comment_notification(comment)
        except Exception:
            pass
        messages.success(request, 'Комментарий добавлен!')
        return redirect(page.get_absolute_url()) + f'#comment-{comment.pk}'
    return JsonResponse({'errors': form.errors}, status=400)


def add_reply(request, slug, comment_pk):
    page = get_object_or_404(Page, slug=slug, status=Page.PUBLISHED)
    parent = get_object_or_404(Comment, pk=comment_pk, page=page)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    form = ReplyForm(request.POST, parent=parent)
    if form.data.get('honeypot'):
        return JsonResponse({'error': 'Spam detected'}, status=400)
    if form.is_valid():
        reply = form.save(commit=False)
        reply.page = page
        reply.parent = parent
        if request.user.is_authenticated:
            reply.author = request.user
            reply.name = request.user.get_full_name() or request.user.get_username()
        reply.save()
        cache.delete(f'comments:{slug}')
        messages.success(request, 'Ответ добавлен!')
        return redirect(page.get_absolute_url()) + f'#comment-{reply.pk}'
    return JsonResponse({'errors': form.errors}, status=400)


def _send_comment_notification(comment):
    from django.core.mail import send_mail
    from django.conf import settings

    site_email = SiteSetting.objects.filter(key='site_email').first()
    if not site_email:
        return

    send_mail(
        subject=f'Новый комментарий к странице: {comment.page.title}',
        message=f'Имя: {comment.name or "Аноним"}\nEmail: {comment.email or "Не указан"}\n\n{comment.text}\n\n{comment.page.get_absolute_url()}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[site_email.value],
        fail_silently=True,
    )


# ==================== Subscriptions ====================

def subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if email:
            obj, created = Subscription.objects.get_or_create(email=email)
            if created:
                messages.success(request, 'Вы подписались на обновления!')
            else:
                messages.info(request, 'Этот email уже подписан.')
        else:
            messages.error(request, 'Введите email.')
    return redirect('home')


def unsubscribe(request, uid):
    try:
        sub = get_object_or_404(Subscription, pk=uid)
        sub.active = False
        sub.save()
        messages.info(request, 'Вы отписались от обновлений.')
    except Exception:
        messages.error(request, 'Не удалось отписаться.')
    return redirect('home')


# ==================== Gallery ====================

def gallery_list(request):
    cache_key = 'gallery_list'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    galleries = list(MediaGallery.active_objects.select_related('category')[:50])
    context = {'galleries': galleries, 'page_title': 'Медиа-галерея'}
    response = render(request, 'pages/gallery.html', context)
    cache.set(cache_key, response, 900)
    return response


def gallery_detail(request, pk):
    gallery = get_object_or_404(MediaGallery, pk=pk, is_active=True)
    related_ids = list(
        MediaGallery.active_objects.exclude(pk=gallery.pk).values_list('pk', 'title', 'image', 'created_at')[:8]
    )
    # Преобразуем кортежи обратно в объекты по pk
    related_pks = [r[0] for r in related_ids]
    related = list(MediaGallery.active_objects.filter(pk__in=related_pks).select_related('category').order_by('-created_at'))

    context = {'gallery': gallery, 'related': related}
    return render(request, 'pages/gallery_detail.html', context)
