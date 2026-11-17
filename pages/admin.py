"""
Административная панель для управления страницами.
"""
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from datetime import timedelta
from .models import Page, PageCategory, PageBlock, SiteSetting, Comment, Subscription, MediaGallery


@admin.register(PageCategory)
class PageCategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'page_count', 'gallery_count', 'is_active', 'updated_at']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title', 'description']
    list_filter = ['is_active', 'created_at']

    def page_count(self, obj):
        return obj.pages.count()
    page_count.short_description = 'Количество страниц'
    page_count.admin_order_field = 'page_count'

    def gallery_count(self, obj):
        return obj.gallery.count()
    gallery_count.short_description = 'Фото в галерее'
    gallery_count.admin_order_field = 'gallery_count'


class PageBlockInline(admin.TabularInline):
    model = PageBlock
    extra = 1
    verbose_name = 'Блок контента'
    verbose_name_plural = 'Блоки контента'


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'status_badge', 'category', 'view_count', 'published_at', 'updated_at']
    list_filter = ['status', 'is_featured', 'category', 'published_at', 'created_at']
    search_fields = ['title', 'excerpt', 'content']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['author']
    date_hierarchy = 'published_at'
    list_editable = ['status']
    inlines = [PageBlockInline]
    readonly_fields = ['view_count', 'created_at', 'updated_at']

    def status_badge(self, obj):
        if obj.status == Page.PUBLISHED:
            return format_html('<span style="color:green;">✓ Опубликовано</span>')
        return format_html('<span style="color:red;">✗ Черновик</span>')
    status_badge.short_description = 'Статус'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(PageBlock)
class PageBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'page', 'ordering', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'page__title']


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ['label', 'key', 'updated_at']
    list_filter = ['key']
    search_fields = ['label', 'key']
    readonly_fields = ['updated_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'page_title', 'status', 'is_spam', 'created_at']
    list_filter = ['status', 'is_spam', 'created_at']
    search_fields = ['name', 'email', 'text', 'page__title']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_comments', 'reject_comments', 'mark_as_spam']

    def page_title(self, obj):
        return obj.page.title
    page_title.short_description = 'Страница'
    page_title.admin_order_field = 'page__title'

    def approve_comments(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f'Одобreno {queryset.count()} комментарий(ов)', messages.SUCCESS)
    approve_comments.short_description = 'Одобрить выбранные'

    def reject_comments(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'Отклонено {queryset.count()} комментарий(ов)', messages.WARNING)
    reject_comments.short_description = 'Отклонить выбранные'

    def mark_as_spam(self, request, queryset):
        queryset.update(status='rejected', is_spam=True)
        self.message_user(request, f'Помечено как спам: {queryset.count()} комментарий(ов)', messages.ERROR)
    mark_as_spam.short_description = 'Отметить как спам'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['email', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['email']


@admin.register(MediaGallery)
class MediaGalleryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'thumbnail', 'is_active', 'created_at']
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['thumbnail']
    list_editable = ['is_active']

    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return '(Нет изображения)'
    thumbnail.short_description = 'Превью'


# Admin site custom config
admin.site.site_header = 'DynamicPages Admin'
admin.site.site_title = 'DynamicPages Admin Panel'
admin.site.index_title = 'Управление динамическими страницами'
