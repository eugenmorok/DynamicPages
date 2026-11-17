from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
from .managers import PublishedPageManager, ActiveCommentManager, ActiveMediaGalleryManager


class PageCategory(models.Model):
    """Категория страницы (раздел сайта)."""
    title = models.CharField('Название', max_length=200, db_index=True)
    slug = models.SlugField('URL-адрес', max_length=200, unique=True, db_index=True)
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'Категория страницы'
        verbose_name_plural = 'Категории страниц'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:category_detail', kwargs={'slug': self.slug})


class Page(models.Model):
    """Динамическая страница сайта."""
    PUBLISHED = 'published'
    DRAFT = 'draft'
    STATUS_CHOICES = [
        (PUBLISHED, 'Опубликована'),
        (DRAFT, 'Черновик'),
    ]

    title = models.CharField('Заголовок', max_length=300, db_index=True)
    slug = models.SlugField('URL-адрес', max_length=300, unique=True, db_index=True)
    category = models.ForeignKey(
        PageCategory,
        on_delete=models.CASCADE,
        related_name='pages',
        verbose_name='Категория',
        null=True,
        blank=True,
    )
    content = CKEditor5Field('Содержание', 'default', blank=True)
    excerpt = models.TextField('Краткое описание', blank=True, max_length=500)
    meta_title = models.CharField('Meta Title', max_length=200, blank=True)
    meta_description = models.TextField('Meta Description', blank=True, max_length=500)
    meta_keywords = models.CharField('Meta Keywords', max_length=300, blank=True)
    featured_image = models.ImageField('Изображение', upload_to='pages/%Y/%m/', blank=True, null=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        db_index=True,
    )
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        related_name='pages',
        verbose_name='Автор',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    published_at = models.DateTimeField('Опубликовано', null=True, blank=True)
    is_featured = models.BooleanField('Рекомендуемая', default=False)
    view_count = models.PositiveIntegerField('Просмотры', default=0)

    # Custom managers
    objects = models.Manager()  # Full manager
    published_objects = PublishedPageManager()  # Only published, pre-optimized

    class Meta:
        ordering = ['-published_at']
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        indexes = [
            models.Index(fields=['title', 'slug']),
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['category', 'status']),
            # Composite index for featured pages optimization
            models.Index(fields=['is_featured', 'published_at'], name='featured_pages_idx'),
            # Covering index for list views
            models.Index(fields=['status', 'published_at', 'title', 'slug', 'category_id'], name='page_list_covering'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Page.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        if self.status == self.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('pages:page_detail', kwargs={'slug': self.slug})

    def increment_view_count(self):
        Page.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
        self.view_count += 1

    def __eq__(self, other):
        if not isinstance(other, Page):
            return False
        if self.pk is None or other.pk is None:
            return self.title == other.title and self.category == other.category
        return self.pk == other.pk

    def get_status_display_badge(self):
        if self.status == self.PUBLISHED:
            return 'success'
        return 'secondary'

    def get_approved_comments(self):
        """Оптимизированная загрузка одобренных комментариев с репликациями."""
        return Comment.objects.filter(
            page=self,
            status='approved',
            is_spam=False,
        ).select_related('author').order_by('-created_at')


class PageBlock(models.Model):
    """Дополнительный блок контента страницы."""
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='blocks')
    title = models.CharField('Заголовок', max_length=200, blank=True)
    content = CKEditor5Field('Содержание', 'default', blank=True)
    image = models.ImageField('Изображение', upload_to='blocks/%Y/%m/', blank=True, null=True)
    ordering = models.PositiveSmallIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        ordering = ['ordering']
        verbose_name = 'Блоки страницы'
        verbose_name_plural = 'Блоки страниц'

    def __str__(self):
        return f'{self.page.title} — {self.title or "Без заголовка"}'


class SiteSetting(models.Model):
    """Глобальные настройки сайта."""
    KEY_CHOICES = [
        ('site_title', 'Название сайта'),
        ('site_description', 'Описание сайта'),
        ('site_email', 'Email сайта'),
        ('site_phone', 'Телефон сайта'),
        ('site_address', 'Адрес сайта'),
        ('facebook_url', 'Facebook URL'),
        ('twitter_url', 'Twitter URL'),
        ('instagram_url', 'Instagram URL'),
        ('youtube_url', 'YouTube URL'),
        ('analytics_id', 'ID аналитики'),
        ('custom_css', 'Пользовательский CSS'),
    ]
    key = models.CharField('Ключ', max_length=50, choices=KEY_CHOICES, unique=True)
    value = models.TextField('Значение', blank=True)
    label = models.CharField('Название', max_length=100)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Настройка сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return self.label

    @classmethod
    def get_value(cls, key, default=''):
        """Получить значение настройки с кэшированием."""
        cache_key = f'setting:{key}'
        from django.core.cache import cache
        value = cache.get(cache_key)
        if value is None:
            try:
                value = cls.objects.get(key=key).value
                cache.set(cache_key, value, 300)
            except cls.DoesNotExist:
                value = default
        return value


class Comment(models.Model):
    """Комментарий к странице."""
    STATUS_CHOICES = [
        ('pending', 'На модерации'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонён'),
    ]

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Страница',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='Ответ',
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        related_name='comments',
        verbose_name='Автор',
        null=True,
        blank=True,
    )
    email = models.EmailField('Email (не публикуется)', blank=True)
    name = models.CharField('Имя', max_length=100, blank=True)
    text = models.TextField('Текст', max_length=5000)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    is_spam = models.BooleanField('Спам', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    objects = models.Manager()  # Full manager (not published-only)
    active_objects = ActiveCommentManager()  # Pre-optimized approved comments

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        indexes = [
            models.Index(fields=['page', 'status']),
            models.Index(fields=['page', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            # Covering index for approved comments list
            models.Index(fields=['page', 'status', 'created_at', 'text', 'name', 'author_id'], name='comment_meta_covering'),
        ]

    def __str__(self):
        return f'{self.name or "Аноним"} → {self.page.title}'

    def get_replies(self):
        return self.replies.filter(status='approved')

    def replies_count(self):
        return self.replies.filter(status='approved').count()

    def get_absolute_url(self):
        return self.page.get_absolute_url()


class Subscription(models.Model):
    """Подписка на обновления сайта."""
    email = models.EmailField('Email', unique=True, db_index=True)
    active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        indexes = [
            models.Index(fields=['email', 'active']),
        ]

    def __str__(self):
        return f'{self.email} ({self.active})'


class MediaGallery(models.Model):
    """Медиа-галерея сайта."""
    title = models.CharField('Заголовок', max_length=200)
    description = models.TextField('Описание', blank=True, default='')
    image = models.ImageField('Изображение', upload_to='gallery/%Y/%m/')
    category = models.ForeignKey(
        PageCategory,
        on_delete=models.SET_NULL,
        related_name='gallery',
        verbose_name='Категория',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    is_active = models.BooleanField('Активна', default=True)
    thumbnail = models.ImageField('Миниатюра', upload_to='gallery/thumbs/%Y/%m/', blank=True, null=True)

    # Custom managers
    objects = models.Manager()  # Full manager
    active_objects = ActiveMediaGalleryManager()  # Pre-optimized active items

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Галерея'
        verbose_name_plural = 'Галерея'
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['category', 'is_active', 'created_at'], name='gallery_category_covering'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:gallery_detail', kwargs={'slug': self.pk})

    def save(self, *args, **kwargs):
        # Удаляем старый thumbnail при обновлении изображения
        was_existing = self.pk is not None
        if was_existing:
            old = MediaGallery.objects.filter(pk=self.pk).only('thumbnail').first()
            if old and old.thumbnail != self.thumbnail:
                old.thumbnail.delete(save=False)
        super().save(*args, **kwargs)
        self._generate_thumbnail()

    def _generate_thumbnail(self):
        """Генерация миниатюры для изображения (120x120)."""
        from django.conf import settings
        from PIL import Image as PILImage
        from io import BytesIO
        from django.core.files.base import ContentFile
        import os

        if not self.image:
            return

        try:
            img = PILImage.open(self.image.file)
            img.thumbnail((120, 120), PILImage.LANCZOS)

            # Сохранить в PNG
            buf = BytesIO()
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=85)
            buf.seek(0)

            thumb_name = f'{os.path.splitext(self.image.name)[0]}_thumb.jpg'
            self.thumbnail.save(thumb_name, ContentFile(buf.read()), save=False)
            buf.close()
        except Exception:
            pass  # Fail gracefully — image still works without thumbnail

