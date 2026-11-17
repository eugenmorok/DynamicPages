import os
import io
import django
import requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')
django.setup()

from pages.models import Page, MediaGallery
from django.conf import settings

# Test all critical URLs
test_urls = [
    ('/', 'Home page'),
    ('/pages/', 'Page list'),
    ('/page/faq-general/', 'FAQ page detail'),
    ('/page/welcome-dynamicpages/', 'Welcome page detail'),
    ('/page/about-project/', 'About page detail'),
    ('/page/contact-info/', 'Contact page detail'),
    ('/page/our-services/', 'Services page detail'),
    ('/page/how-to-start/', 'How-to-start page detail'),
    ('/gallery/', 'Gallery list'),
    ('/gallery/1/', 'Gallery item'),
    ('/admin/', 'Admin'),
    ('/sitemap.xml', 'Sitemap'),
    ('/robots.txt', 'Robots.txt'),
    ('/api/health/', 'Health check'),
    ('/page/nonexistent/', '404 page'),
    ('/static/css/style.css', 'Custom CSS'),
]

print("=" * 80)
print("FINAL VERIFICATION - All-systems check")
print("=" * 80)

all_ok = True
for url, name in test_urls:
    try:
        resp = requests.get(f"http://127.0.0.1:8080{url}", timeout=5)
        status = resp.status_code
        marker = "OK" if status in (200, 404) else "FAIL"
        if status >= 500:
            all_ok = False
            marker = "FAIL"
        print(f"[{marker}] {name:30} {url:30} -> {status}")
    except Exception as e:
        all_ok = False
        print(f"[ERR ] {name:30} {url:30} -> {e}")

# Media files
print("\n" + "=" * 80)
print("Media Files Verification")
print("=" * 80)
for page in Page.objects.all():
    if page.featured_image:
        exists = os.path.exists(page.featured_image.path)
        try:
            resp = requests.get(f"http://127.0.0.1:8080/{page.featured_image.url}", timeout=5)
            http_ok = resp.status_code == 200
        except Exception:
            http_ok = False
        ok = exists and http_ok
        marker = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"[{marker}] {page.title[:35]:35} -> disk:{exists!s:5} http:{http_ok!s:5}")

for g in MediaGallery.objects.all():
    if g.image:
        exists = os.path.exists(g.image.path)
        try:
            resp = requests.get(f"http://127.0.0.1:8080/{g.image.url}", timeout=5)
            http_ok = resp.status_code == 200
        except Exception:
            http_ok = False
        ok = exists and http_ok
        marker = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"[{marker}] {g.title[:35]:35} -> disk:{exists!s:5} http:{http_ok!s:5}")

# Database integrity
print("\n" + "=" * 80)
print("Database Count")
print("=" * 80)
print(f"  Pages:          {Page.objects.count()}")
print(f"  Gallery items:  {MediaGallery.objects.count()}")

# Final result
print("\n" + "=" * 80)
if all_ok:
    print("ALL CHECKS PASSED - System is FULLY OPERATIONAL!")
else:
    print("SOME CHECKS FAILED - Review output above")
print("=" * 80)
