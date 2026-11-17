"""
Административная панель для управления страницами.
"""
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Page, PageCategory, PageBlock, SiteSetting, Comment, Subscription, MediaGallery


# ============================================================
# SiteSetting: collapsible key-value interface
# ============================================================

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ['label', 'key', 'updated_at']
    list_filter = ['key']
    search_fields = ['label', 'key']
    readonly_fields = ['updated_at']
    fields = ['label', 'key', 'value', 'updated_at']
    ordering = ['key']


# ============================================================
# MediaGallery with image preview
# ============================================================

@admin.register(MediaGallery)
class MediaGalleryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'thumbnail', 'is_active', 'created_at']
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['title', 'description', 'image']
    readonly_fields = ['thumbnail']
    list_editable = ['is_active']
    list_per_page = 20
    
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return '(Нет изображения)'
    thumbnail.short_description = 'Превью'


# ============================================================
# Subscription: email management
# ============================================================

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['email', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['email']
    list_per_page = 25


# ============================================================
# PageBlock: simplified inline for admin
# ============================================================

class PageBlockInline(admin.TabularInline):
    model = PageBlock
    extra = 1
    verbose_name = 'Блок контента'
    verbose_name_plural = 'Блоки контента'
    fields = ('block_type', 'title', 'content')
    readonly_fields = ()


# ============================================================
# PageCategory: smart admin
# ============================================================

@admin.register(PageCategory)
class PageCategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'page_count', 'gallery_count', 'is_active', 'updated_at']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title', 'description']
    list_filter = ['is_active', 'created_at']
    list_per_page = 20
    
    def page_count(self, obj):
        return obj.pages.count()
    page_count.short_description = 'Количество страниц'
    page_count.admin_order_field = 'page_count'
    
    def gallery_count(self, obj):
        return obj.gallery.count()
    gallery_count.short_description = 'Фото в галерее'
    gallery_count.admin_order_field = 'gallery_count'


# ============================================================
# Page: comprehensive admin interface
# ============================================================

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
    list_per_page = 25
    
    actions = ['publish_selected', 'unpublish_selected', 'reset_view_counts', 'featured_selected']
    
    def status_badge(self, obj):
        if obj.status == Page.PUBLISHED:
            return format_html('<span style="color:green;">✓ Опубликовано</span>')
        return format_html('<span style="color:red;">✗ Черновик</span>')
    status_badge.short_description = 'Статус'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    def publish_selected(self, request, queryset):
        rows_updated = queryset.filter(status=Page.DRAFT).update(status=Page.PUBLISHED)
        self.message_user(request, f'Опубликовано {rows_updated} страниц(а)', messages.SUCCESS)
    publish_selected.short_description = 'Опубликовать выбранные'
    
    def unpublish_selected(self, request, queryset):
        rows_updated = queryset.filter(status=Page.PUBLISHED).update(status=Page.DRAFT)
        self.message_user(request, f'Отчерновено {rows_updated} страниц(а)', messages.WARNING)
    unpublish_selected.short_description = 'Отменить публикацию'
    
    def reset_view_counts(self, request, queryset):
        rows_updated = queryset.update(view_count=0)
        self.message_user(request, f'Сброшено посещение для {rows_updated} страниц(а)', messages.INFO)
    reset_view_counts.short_description = 'Сбросить счётчик просмотров'
    
    def featured_selected(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f'Отмечено как избранное: {queryset.count()} страниц(а)', messages.SUCCESS)
    featured_selected.short_description = 'Отметить как избранное'


# ============================================================
# Comment: moderation tools
# ============================================================

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'page_title', 'status', 'is_spam', 'created_at']
    list_filter = ['status', 'is_spam', 'created_at']
    search_fields = ['name', 'email', 'text', 'page__title']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_comments', 'reject_comments', 'mark_as_spam', 'unmark_as_spam']
    list_per_page = 25
    
    def page_title(self, obj):
        return obj.page.title
    page_title.short_description = 'Страница'
    page_title.admin_order_field = 'page__title'
    
    def approve_comments(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f'Одобрено {queryset.count()} комментарий(ов)', messages.SUCCESS)
    approve_comments.short_description = 'Одобрить выбранные'
    
    def reject_comments(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'Отклонено {queryset.count()} комментарий(ов)', messages.WARNING)
    reject_comments.short_description = 'Отклонить выбранные'
    
    def mark_as_spam(self, request, queryset):
        queryset.update(status='rejected', is_spam=True)
        self.message_user(request, f'Помечено как спам: {queryset.count()} комментарий(ов)', messages.ERROR)
    mark_as_spam.short_description = 'Отметить как спам'
    
    def unmark_as_spam(self, request, queryset):
        queryset.update(status='approved', is_spam=False)
        self.message_user(request, f'Снята пометка спам: {queryset.count()} комментарий(ов)', messages.INFO)
    unmark_as_spam.short_description = 'Снять пометку спам'
