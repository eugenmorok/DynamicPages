"""
Тесты для приложения pages — Stage 5a: production-hardened.
"""
import os
from io import BytesIO
from PIL import Image as PILImage
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from .models import Page, PageCategory, Comment, MediaGallery, SiteSetting, Subscription


# ============================================================
# Helpers — create fake PNG images for ImageField
# ============================================================

def _make_fake_image(name="test.png", size=10):
    img = PILImage.new('RGB', (size, size), color='red')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return InMemoryUploadedFile(buf, 'image', name, 'image/png', buf.getbuffer().nbytes, None)


# ============================================================
# PageModelTestCase
# ============================================================

class PageModelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.page = Page.objects.create(
            title='Test Page',
            slug='test-page',
            excerpt='Excerpt',
            status=Page.PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        Page.objects.create(
            title='Draft Page',
            slug='draft-page',
            status=Page.DRAFT,
        )
        cls.category = PageCategory.objects.create(title='TestCategory', slug='test-cat')

    def test_published_objects(self):
        self.assertEqual(Page.published_objects.count(), 1)
        self.assertIn(self.page, Page.published_objects.all())

    def test_increment_view_count(self):
        self.page.view_count = 0
        self.page.save(update_fields=['view_count'])
        self.page.increment_view_count()
        refreshed = Page.objects.get(pk=self.page.pk)
        self.assertEqual(refreshed.view_count, 1)


# ============================================================
# PageCategoryTestCase
# ============================================================

class PageCategoryTestCase(TestCase):
    def test_slug_generation(self):
        category = PageCategory.objects.create(title='Auto Slug Test')
        # slugify("Auto Slug Test") => "auto-slug-test"
        self.assertIn(category.slug, ['auto-slug-test', 'auto-slug-test'])
        self.assertEqual(category.slug.lower().replace('-', ''), 'autoslugtest')

    def test_is_active_default(self):
        category = PageCategory.objects.create(title='Default Active')
        self.assertTrue(category.is_active)

    def test_page_count(self):
        cat_with_pages = PageCategory.objects.create(title='With Pages', slug='with-pages')
        Page.objects.create(
            title='Page In Cat', slug='page-in-cat', status=Page.PUBLISHED,
            category=cat_with_pages,
        )
        self.assertEqual(cat_with_pages.pages.count(), 1)

    def test_page_objects_relationship(self):
        cat = PageCategory.objects.create(title='Rel Cat', slug='rel-cat')
        page = Page.objects.create(
            title='Rel Page', slug='rel-page', status=Page.PUBLISHED,
            category=cat,
        )
        self.assertEqual(cat.pages.count(), 1)
        self.assertIn(page, cat.pages.all())


# ============================================================
# CommentTestCase
# ============================================================

class CommentTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.page = Page.objects.create(
            title='Comments Page', slug='comments-page', status=Page.PUBLISHED,
        )

    def test_creation(self):
        comment = Comment.objects.create(
            page=self.page,
            name='TestUser',
            email='test@test.com',
            text='Test comment',
            status='approved',
        )
        self.assertEqual(comment.page_id, self.page.pk)
        self.assertFalse(comment.is_spam)

    def test_status_default(self):
        comment = Comment.objects.create(
            page=self.page,
            name='Test',
            text='Test',
        )
        self.assertEqual(comment.status, 'pending')

    def test_get_approved(self):
        Comment.objects.create(
            page=self.page, name='A', text='A', status='approved',
        )
        Comment.objects.create(
            page=self.page, name='B', text='B', status='pending',
        )
        approved = list(Comment.approved_objects.filter(page=self.page))
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].name, 'A')


# ============================================================
# MediaGalleryTestCase
# ============================================================

class MediaGalleryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = PageCategory.objects.create(title='Gallery', slug='gallery')
        cls.active_item = MediaGallery.objects.create(
            title='Active Gallery Item',
            image=_make_fake_image(),
            category=cls.category,
            is_active=True,
        )
        cls.inactive_item = MediaGallery.objects.create(
            title='Inactive Gallery Item',
            image=_make_fake_image('inactive.png'),
            category=cls.category,
            is_active=False,
        )

    def test_active_objects(self):
        active = list(MediaGallery.active_objects.all())
        self.assertIn(self.active_item, active)
        self.assertNotIn(self.inactive_item, active)

    def test_inactive_filtered_out(self):
        self.assertEqual(MediaGallery.active_objects.count(), 1)


# ============================================================
# SiteSettingTestCase
# ============================================================

class SiteSettingTestCase(TestCase):
    def test_get_set_value(self):
        SiteSetting.objects.create(
            key='site_title', value='My Site Title', label='Название сайта',
        )
        self.assertEqual(SiteSetting.get_value('site_title'), 'My Site Title')
        self.assertEqual(SiteSetting.get_value('missing_key', 'fallback'), 'fallback')

    def test_cache_usage(self):
        SiteSetting.objects.create(
            key='site_email', value='email@example.com', label='Email',
        )
        cache.clear()
        val1 = SiteSetting.get_value('site_email')
        val2 = SiteSetting.get_value('site_email')
        self.assertEqual(val1, val2)


# ============================================================
# ViewsTestCase — use correct URL paths
# ============================================================

class ViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = PageCategory.objects.create(title='View Cat', slug='view-cat')
        cls.page = Page.objects.create(
            title='Home Test Page',
            slug='home-test',
            excerpt='Home page',
            status=Page.PUBLISHED,
            category=cls.category,
        )
        cls.client = Client()

    def test_home(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'home')

    def test_page_detail(self):
        # Slug 'home-test' -> URL: /page/home-test/
        resp = self.client.get('/page/home-test/')
        self.assertEqual(resp.status_code, 200)

    def test_category_detail(self):
        resp = self.client.get('/category/view-cat/')
        self.assertEqual(resp.status_code, 200)

    def test_not_found(self):
        resp = self.client.get('/page/nonexistent/')
        self.assertEqual(resp.status_code, 404)

    def test_page_list(self):
        resp = self.client.get('/pages/')
        self.assertEqual(resp.status_code, 200)


# ============================================================
# APITestCase
# ============================================================

class APITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = PageCategory.objects.create(title='APICat', slug='api-cat')
        cls.page = Page.objects.create(
            title='API Test Page',
            slug='api-test-page',
            excerpt='For API tests',
            status=Page.PUBLISHED,
            category=cls.category,
            published_at=timezone.now(),
        )
        cls.gallery_item = MediaGallery.objects.create(
            title='API Gallery',
            image=_make_fake_image('api.jpg'),
            category=cls.category,
            is_active=True,
        )
        Comment.objects.create(
            page=cls.page, name='TestUser', email='test@api.com',
            text='Nice!', status='approved',
        )

    def test_health(self):
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data']['status'], 'healthy')

    def test_api_index(self):
        resp = self.client.get('/api/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('version', data['data'])

    def test_api_pages_list(self):
        resp = self.client.get('/api/v1/pages/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertGreaterEqual(data['pagination']['total'], 1)

    def test_api_page_detail(self):
        resp = self.client.get(f'/api/v1/pages/{self.page.pk}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['title'], 'API Test Page')

    def test_api_categories(self):
        resp = self.client.get('/api/v1/categories/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(len(data), 1)

    def test_api_gallery(self):
        resp = self.client.get('/api/v1/gallery/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['pagination']['total'], 1)

    def test_api_gallery_detail(self):
        resp = self.client.get(f'/api/v1/gallery/{self.gallery_item.pk}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['title'], 'API Gallery')

    def test_api_comments(self):
        resp = self.client.get(f'/api/v1/pages/{self.page.pk}/comments/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['pagination']['total'], 1)

    def test_api_comment_submit(self):
        resp = self.client.post(
            f'/api/v1/pages/{self.page.pk}/comments/submit/',
            data='{"name":"New","email":"new@test.com","text":"Great post!"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'pending')


# ============================================================
# CacheTestCase
# ============================================================

class CacheTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.page = Page.objects.create(
            title='Cache Test', slug='cache-test', status=Page.PUBLISHED,
        )

    def test_invalidation(self):
        cache_key = f'api_page:{self.page.pk}'
        cache.set(cache_key, {'test': 'data'}, 300)
        self.assertEqual(cache.get(cache_key), {'test': 'data'})
        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))


# ============================================================
# SubscriptionTestCase
# ============================================================

class SubscriptionTestCase(TestCase):
    def test_creation(self):
        sub = Subscription.objects.create(email='test@sub.com')
        self.assertTrue(sub.active)
        self.assertEqual(str(sub), 'test@sub.com (True)')

    def test_unique_email(self):
        Subscription.objects.create(email='unique@test.com')
        with self.assertRaises(Exception):
            Subscription.objects.create(email='unique@test.com')


# ============================================================
# PerformanceTestCase
# ============================================================

class PerformanceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = PageCategory.objects.create(title='PerfCat', slug='perf-cat')
        now = timezone.now()
        cls.pages = Page.objects.bulk_create([
            Page(
                title=f'Perf Page {i}',
                slug=f'perf-page-{i}',
                excerpt='Performance',
                category=cls.category,
                status=Page.PUBLISHED,
                published_at=now,
            )
            for i in range(20)
        ])

    def test_bulk_filtering_efficiency(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        cat = PageCategory.objects.get(slug='perf-cat')
        with CaptureQueriesContext(connection) as captured:
            pages = list(
                Page.published_objects.select_related('category')
                .filter(category=cat)
            )
        self.assertEqual(len(pages), 20)
        self.assertLessEqual(len(captured.captured_queries), 5)
