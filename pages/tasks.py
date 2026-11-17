"""
Celery конфигурация для асинхронных задач.
- Генерация thumbnail
- Отправка email уведомлений
- Подписка на обновления (email digest)
"""
import os
from celery import Celery

# Настройка Celery для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')

app = Celery('dynamicpages')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автопоиск задач из всех установленных app
app.autodiscover_tasks()


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_thumbnail(self, gallery_id):
    """Асинхронная генерация миниатюры."""
    from PIL import Image as PILImage
    from io import BytesIO
    from django.core.files.base import ContentFile
    from django.conf import settings
    from .models import MediaGallery
    import os

    try:
        gallery = MediaGallery.objects.get(pk=gallery_id)
        if not gallery.image:
            return 'Skipped: no image'

        img = PILImage.open(gallery.image.file)
        img.thumbnail((120, 120), PILImage.LANCZOS)

        buf = BytesIO()
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format='JPEG', quality=85)
        buf.seek(0)

        thumb_name = f'{os.path.splitext(gallery.image.name)[0]}_thumb.jpg'
        gallery.thumbnail.save(thumb_name, ContentFile(buf.read()), save=False)
        gallery.save(update_fields=['thumbnail'])

        return f'Thumbnail generated for {gallery.title}'
    except MediaGallery.DoesNotExist:
        return f'Gallery {gallery_id} not found'
    except Exception:
        # Retry on failure
        raise self.retry(countdown=60)


@app.task(bind=True, max_retries=5, default_retry_delay=30)
def send_email_notification(self, comment_id):
    """Отправка email уведомления о новом комментарии."""
    from django.core.mail import send_mail
    from django.conf import settings
    from .models import Comment, SiteSetting

    try:
        comment = Comment.objects.select_related('page').get(pk=comment_id)
        site_email = SiteSetting.objects.filter(key='site_email').first()
        if not site_email:
            return 'No site_email set'

        subject = f'Новый комментарий к странице: {comment.page.title}'
        body = f'''
Имя: {comment.name or 'Аноним'}
Email: {comment.email or 'Не указан'}

Текст комментария:
{comment.text}

Пр permalink: {comment.page.get_absolute_url()}
'''
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[site_email.value],
            fail_silently=False,
        )
        return f'Email sent for comment {comment_id}'
    except Comment.DoesNotExist:
        return 'Comment not found'
    except Exception:
        raise self.retry(countdown=30)


@app.task(bind=True)
def send_subscription_digest(self):
    """Отправка дайджеста подписчикам. Выполняется по расписанию."""
    from .models import Subscription, Page
    from django.core.mail import send_mass_mail
    from django.conf import settings
    from django.utils import timezone

    # Получаем последних 10 опубликованных страниц
    new_pages = Page.published_objects.filter(
        published_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).order_by('-published_at')[:10]

    if not new_pages:
        return 'No new pages this week'

    active_subs = Subscription.objects.filter(active=True)
    emails = []

    for sub in active_subs[:1000]:  # Limit to 1000 emails to avoid overload
        page_list = '\n'.join(
            f'  - {p.title}: {p.get_absolute_url()}' for p in new_pages
        )
        body = f'''
Еженедельный дайджест DynamicPages:

Новые страницы за последнюю неделю:

{page_list}

Спасибо, что вы с нами!
'''
        emails.append(
            ('Еженедельный дайджест', body, settings.DEFAULT_FROM_EMAIL, [sub.email])
        )

    if emails:
        send_mass_email(emails)
        return f'Sent digest to {len(emails)} subscribers'
    return 'No active subscribers'


@app.task
def cleanup_old_subscriptions():
    """Удаление неактивных подписок старше 2 лет."""
    from django.utils import timezone
    from .models import Subscription

    two_years_ago = timezone.now() - timezone.timedelta(days=730)
    old_subs = Subscription.objects.filter(active=False, created_at__lt=two_years_ago)
    count = old_subs.count()
    old_subs.delete()
    return f'Cleaned up {count} old subscriptions'


@app.task
def analytics_aggregate(start_date, end_date):
    """Агрегация аналитики за период."""
    from .models import Page
    from calendar import timegm
    from datetime import datetime

    # Страницы с наибольшим числом просмотров
    top_pages = list(
        Page.published_objects.values('title', 'slug')
        .annotate(total_views=Count('view_count'))
        .order_by('-total_views')[:10]
    )

    # Страницы с наибольшей активностью
    pages_with_most_comments = list(
        Page.published_objects.values('title', 'slug')
        .annotate(comment_count=Count('comments', filter=Q(comments__status='approved')))
        .order_by('-comment_count')[:10]
    )

    return {
        'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
        'top_pages': top_pages,
        'most_commented': pages_with_most_comments,
    }
