"""
Основной модуль вьюх для управления динамическими страницами.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import models
from django.db.models import Q, Count
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse

from .models import (
    Page, PageCategory, PageBlock, SiteSetting, 
    Comment, Subscription, MediaGallery,
)
from .forms import PageForm, PageCategoryForm, PageBlockForm, SearchForm
from .comments import CommentForm, ReplyForm


# ==================== Public Views ====================

def home(request):
    """Главная страница — последние опубликованные страницы + статистика."""
    published_pages = Page.objects.filter(
        status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    ).select_related('category').order_by('-published_at')[:12]

    categories = PageCategory.objects.filter(
        is_active=True
    ).annotate(page_count=Count('pages')).order_by('title')

    featured_pages = Page.objects.filter(
        status=Page.PUBLISHED,
        is_featured=True,
        published_at__lte=timezone.now(),
    ).select_related('category')[:4]

    context = {
        'published_pages': published_pages,
        'categories': categories,
        'featured_pages': featured_pages,
        'site_title': SiteSetting.get_value('site_title', 'DynamicPages'),
        'site_description': SiteSetting.get_value('site_description', ''),
    }
    return render(request, 'home.html', context)


class PageListView(ListView):
    """Список всех опубликованных страниц."""
    model = Page
    template_name = 'pages/list.html'
    context_object_name = 'pages'
    paginate_by = 12

    def get_queryset(self):
        queryset = Page.objects.filter(
            status=Page.PUBLISHED,
            published_at__lte=timezone.now(),
        ).select_related('category').prefetch_related('blocks').order_by('-published_at')

        # Фильтр по категории
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Поиск
        search_q = self.request.GET.get('q', '').strip()
        if search_q:
            queryset = queryset.filter(
                Q(title__icontains=search_q) |
                Q(excerpt__icontains=search_q) |
                Q(content__icontains=search_q)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            category = get_object_or_404(PageCategory, slug=category_slug)
            context['current_category'] = category
            context['page_title'] = 'Страницы раздела: ' + category.title
        else:
            context['page_title'] = 'Все страницы'
        context['search_form'] = SearchForm(self.request.GET)
        return context


def page_detail(request, slug):
    """Детальная страница."""
    page = get_object_or_404(
        Page,
        slug=slug,
        status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    )
    # Используем F-expression для race-condition free обновления
    Page.objects.filter(pk=page.pk).update(view_count=models.F('view_count') + 1)
    page.refresh_from_db()

    # Approved comments (root only, i.e. parent=None)
    page_comments = Comment.objects.filter(
        page=page,
        status='approved',
        parent__isnull=True,
    ).select_related('author').order_by('-created_at')

    # Похожие страницы
    related_qs = Page.objects.filter(
        status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    ).exclude(pk=page.pk).select_related('category')

    if page.category:
        related_qs = related_qs.filter(category=page.category)

    related_pages = related_qs.order_by('-published_at')[:4]

    # Блоки
    blocks = PageBlock.objects.filter(page=page).select_related()

    # Метатеги
    meta_title = page.meta_title or page.title
    meta_description = page.meta_description or page.excerpt or ''

    context = {
        'page': page,
        'related_pages': related_pages,
        'blocks': blocks,
        'page_comments': page_comments,
        'meta_title': meta_title,
        'meta_description': meta_description,
    }
    return render(request, 'pages/detail.html', context)


def category_detail(request, slug):
    """Детальная страница категории."""
    category = get_object_or_404(
        PageCategory,
        slug=slug,
        is_active=True,
    )
    pages = Page.objects.filter(
        category=category,
        status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    ).order_by('-published_at')[:20]

    context = {
        'category': category,
        'pages': pages,
    }
    return render(request, 'pages/category_detail.html', context)


# ==================== Admin Views ====================

class PageCreateView(LoginRequiredMixin, CreateView):
    """Создание новой страницы."""
    model = Page
    form_class = PageForm
    template_name = 'pages/form.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Страница "' + form.instance.title + '" создана!')
        return super().form_valid(form)


class PageUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование страницы."""
    model = Page
    form_class = PageForm
    template_name = 'pages/form.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        messages.success(self.request, 'Страница "' + form.instance.title + '" обновлена!')
        return super().form_valid(form)


class PageDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление страницы."""
    model = Page
    template_name = 'pages/confirm_delete.html'
    success_url = reverse_lazy('pages:home')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Страница "' + self.object.title + '" удалена!')
        return super().delete(request, *args, **kwargs)


def page_block_create(request, page_slug):
    """Добавить блок к странице."""
    page = get_object_or_404(Page, slug=page_slug)
    if request.method == 'POST':
        form = PageBlockForm(request.POST, request.FILES)
        if form.is_valid():
            block = form.save(commit=False)
            block.page = page
            block.save()
            messages.success(request, 'Блоки добавлен!')
            return redirect('pages:page_detail', page.slug)
    else:
        form = PageBlockForm()
    return render(request, 'pages/form_block.html', {'form': form, 'page': page})


def page_block_delete(request, pk):
    """Удалить блок страницы."""
    block = get_object_or_404(PageBlock, pk=pk)
    page_slug = block.page.slug
    if request.method == 'POST':
        block.delete()
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
        messages.success(self.request, 'Категория "' + form.instance.title + '" создана!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = PageCategory
    form_class = PageCategoryForm
    template_name = 'pages/form_category.html'
    success_url = reverse_lazy('pages:home')

    def form_valid(self, form):
        messages.success(self.request, 'Категория "' + form.instance.title + '" обновлена!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = PageCategory
    template_name = 'pages/confirm_delete.html'
    success_url = reverse_lazy('pages:home')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Категория "' + self.object.title + '" удалена!')
        return super().delete(request, *args, **kwargs)


# ==================== API & Extras ====================

def sitemap_xml(request):
    """Простая XML-карта сайта."""
    pages = Page.objects.filter(
        status=Page.PUBLISHED,
        published_at__lte=timezone.now(),
    ).values_list('slug', 'updated_at')

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for slug, date in pages:
        xml.append('  <url><loc>https://example.com/page/' + slug + '/</loc><lastmod>' + date.strftime('%Y-%m-%d') + '</lastmod></url>')
    xml.append('</urlset>')

    return HttpResponse('\n'.join(xml), content_type='application/xml')


def robots_txt(request):
    """Файл robots.txt."""
    content = 'User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap/\n'
    return HttpResponse(content, content_type='text/plain')


def health_check(request):
    """Проверка работоспособности API."""
    return JsonResponse({
        'status': 'ok',
        'pages_count': Page.objects.count(),
        'published_count': Page.objects.filter(status=Page.PUBLISHED).count(),
    })


def page_not_found(request, exception):
    """Кастомная страница 404."""
    return render(request, '404.html', {
        'site_title': SiteSetting.get_value('site_title', 'DynamicPages'),
        'site_description': SiteSetting.get_value('site_description', ''),
    }, status=404)


def server_error(request):
    """Кастомная страница 500."""
    return render(request, '500.html', status=500)


# ==================== Comment Views ====================

def add_comment(request, slug):
    """Add a comment to a page."""
    page = get_object_or_404(Page, slug=slug, status=Page.PUBLISHED)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    form = CommentForm(request.POST, page=page)
    
    # Check honeypot
    if form.data.get('honeypot'):
        return JsonResponse({'error': 'Spam detected'}, status=400)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.page = page
        
        # Set author if logged in
        if request.user.is_authenticated:
            comment.author = request.user
            comment.name = request.user.get_full_name() or request.user.get_username()
            comment.email = request.user.email or ''
        
        comment.save()
        
        # Send email notification (async in production)
        try:
            send_comment_notification(comment)
        except Exception:
            pass  # Silently fail - don't block comment submission
        
        messages.success(request, 'Комментарий добавлен! Он будет опубликован после модерации.')
        return redirect(page.get_absolute_url()) + '#comment-' + str(comment.pk)
    
    return JsonResponse({'errors': form.errors}, status=400)


def add_reply(request, slug, comment_pk):
    """Reply to a comment."""
    page = get_object_or_404(Page, slug=slug, status=Page.PUBLISHED)
    parent = get_object_or_404(Comment, pk=comment_pk, page=page)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    form = ReplyForm(request.POST, parent=parent)
    
    # Check honeypot
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
        
        messages.success(request, 'Ответ добавлен!')
        return redirect(page.get_absolute_url()) + '#comment-' + str(reply.pk)
    
    return JsonResponse({'errors': form.errors}, status=400)


def send_comment_notification(comment):
    """Send email notification about new pending comment."""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = 'Новый комментарий к странице: ' + comment.page.title
    body = 'Имя: {}\nEmail: {}\n\nТекст:\n{}\n\nСтраница: {}'.format(
        comment.name or 'Аноним',
        comment.email or 'Не указан',
        comment.text,
        comment.page.get_absolute_url(),
    )
    
    site_email = SiteSetting.objects.filter(key='site_email').first()
    if not site_email:
        return  # No recipient
    
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[site_email.value],
        fail_silently=True,
    )


# ==================== Subscription Views ====================

def subscribe(request):
    """Subscribe to site updates."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if email:
            obj, created = Subscription.objects.get_or_create(email=email)
            if created:
                messages.success(request, 'Вы успешно подписались на обновления!')
            else:
                messages.info(request, 'Этот email уже подписан.')
        else:
            messages.error(request, 'Введите email.')
    return redirect('home')


def unsubscribe(request, uid):
    """Unsubscribe from updates."""
    try:
        sub = get_object_or_404(Subscription, pk=uid)
        sub.active = False
        sub.save()
        messages.info(request, 'Вы отписались от обновлений.')
    except Exception:
        messages.error(request, 'Не удалось отписаться.')
    return redirect('home')


# ==================== Gallery Views ====================

def gallery_list(request):
    """Gallery page listing."""
    galleries = MediaGallery.objects.filter(is_active=True).select_related('category').order_by('-created_at')
    context = {
        'galleries': galleries,
        'page_title': 'Медиа-галерея',
    }
    return render(request, 'pages/gallery.html', context)


def gallery_detail(request, pk):
    """Gallery item detail."""
    gallery = get_object_or_404(MediaGallery, pk=pk, is_active=True)
    related = MediaGallery.objects.filter(
        is_active=True,
    ).exclude(pk=gallery.pk).order_by('-created_at')[:8]
    context = {
        'gallery': gallery,
        'related': related,
    }
    return render(request, 'pages/gallery_detail.html', context)
