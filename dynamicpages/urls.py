"""
DynamicPages CMS — URL Configuration.
"""
from django.urls import path, include, re_path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

# Media files MUST be before root URL pattern!
urlpatterns = []
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    # CKEditor5 upload
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('', include('pages.urls')),
]
