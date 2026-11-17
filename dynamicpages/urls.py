"""
DynamicPages CMS — URL Configuration.
"""
from django.urls import path, include, re_path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from pages import views, api

# Media files MUST be before root URL pattern!
urlpatterns = []
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    # Admin
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # CKEditor5 upload
    path('ckeditor5/', include('django_ckeditor_5.urls')),
]

# REST API v1
api_patterns = [
    # Pages
    path('pages/', api.api_pages, name='api_pages_list'),
    path('pages/<int:pk>/', api.api_page_detail, name='api_pages_detail'),
    
    # Categories
    path('categories/', api.api_categories, name='api_categories'),
    
    # Gallery
    path('gallery/', api.api_gallery, name='api_gallery_list'),
    path('gallery/<int:pk>/', api.api_gallery_detail, name='api_gallery_detail'),
    
    # Comments
    path('pages/<int:page_id>/comments/', api.api_comments, name='api_comments'),
    path('pages/<int:page_id>/comments/submit/', api.api_submit_comment, name='api_submit_comment'),
    
    # Admin stats
    path('admin/stats/', api.api_admin_stats, name='api_admin_stats'),
]

urlpatterns += [
    # Health check & sitemap
    path('api/health/', api.api_health, name='api_health'),
    path('api/', api.api_index, name='api_index'),
    path('api/v1/', include(api_patterns)),
]

urlpatterns += [
    # Sitemap & robots
    path('sitemap/', views.sitemap_xml, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
]

urlpatterns += [
    # Pages app
    path('', include('pages.urls')),
]
