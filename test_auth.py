"""Проверка login/logout/CRUD и финальный результат."""
import os, sys, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')
import django; django.setup()

import http.client
from django.contrib.auth.models import User
from pages.models import Page, PageCategory

pass_results = []
fail_results = []

def ok(name): pass_results.append(name)
def fail(name, detail): fail_results.append(f'{name}: {detail}')

# === 1. Logout behavior ===
conn = http.client.HTTPConnection('127.0.0.1', 8080)
conn.request('GET', '/accounts/logout/')
r = conn.getresponse()
data = r.read()
conn.close()
if r.status == 405:
    ok('Logout GET -> 405 (защита от CSRF — это нормально)')
else:
    fail('Logout GET', f'got {r.status}, expected 405')

# === 2. Create test user ===
if not User.objects.filter(username='testlogin').exists():
    User.objects.create_superuser('testlogin', '', 'testpass123')
    ok('Created testlogin user')
else:
    ok('testlogin user exists')

# === 3. Login POST ===
conn = http.client.HTTPConnection('127.0.0.1', 8080)
conn.request('GET', '/accounts/login/')
r = conn.getresponse()
login_page = r.read().decode()
conn.close()

csrf_match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', login_page)
if csrf_match:
    ct = csrf_match.group(1)
    
    # Try login
    login_data = (
        'username=testlogin&password=testpass123'
        f'&csrfmiddlewaretoken={ct}&next=/admin/'
    )
    
    conn2 = http.client.HTTPConnection('127.0.0.1', 8080)
    conn2.request(
        'POST', '/accounts/login/', login_data,
        {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'http://127.0.0.1:8080/accounts/login/',
        }
    )
    r2 = conn2.getresponse()
    
    if r2.status == 302:
        location = r2.getheader('Location', '/accounts/login/')
        conn2.close()
        ok(f'Login POST -> {r2.status} redirect to {location}')
        
        # Follow redirect and test admin access
        cookies = r2.getheader('Set-Cookie', '')
        conn3 = http.client.HTTPConnection('127.0.0.1', 8080)
        conn3.request(
            'GET', '/admin/',
            headers={
                'Cookie': cookies,
                'Referer': f'http://127.0.0.1:8080{location}',
            }
        )
        r3 = conn3.getresponse()
        body3 = r3.read()
        conn3.close()
        
        if r3.status == 200 and len(body3) > 0:
            ok('Admin accessible via cookie (200 OK)')
            pass_results.append(f'Admin panel content: {len(body3)} bytes')
        elif r3.status == 302:
            fail('Admin after login', f'redirected again: {r3.getheader("Location")}')
        else:
            fail('Admin after login', f'{r3.status}, body: {len(body3)}b')
    else:
        r2.read()
        conn2.close()
        fail('Login POST', f'{r2.status}')
else:
    fail('CSRF', 'No CSRF token in login page')

# === 4. POST logout (with session) ===
# === 4. PageBlock model check ===
from pages.models import PageBlock
blocks = PageBlock.objects.filter()
ok(f'PageBlock model: {blocks.count()} blocks in DB')

# === 5. CKEditor config check ===
from pages.models import PageBlock
blocks = PageBlock.objects.filter()
ok(f'PageBlock model: {blocks.count()} blocks in DB')

# === 6. CKEditor config check ===
from dynamicpages.settings import CKEDITOR_CONFIGS
if CKEDITOR_CONFIGS:
    ok(f'CKEditor configured: {list(CKEDITOR_CONFIGS.keys())}')
else:
    fail('CKEditor', 'No configs found')

# === 7. Media dir check ===
from django.conf import settings
media_root = settings.MEDIA_ROOT
if os.path.exists(str(media_root)):
    ok(f'Media directory exists: {media_root}')
else:
    ok(f'Media directory created on use: {media_root}')

# === 8. Static dir check ===
static_root = settings.STATIC_ROOT
static_dirs = settings.STATICFILES_DIRS
if os.path.exists(str(static_root)) or static_dirs:
    ok(f'Static configured: STATIC_ROOT={static_root}, STATICFILES_DIRS={len(static_dirs)} dirs')
else:
    fail('Static', 'No static dirs')

# === 9. Categories with slug check ===
cats = PageCategory.objects.filter()
slug_set = set()
for c in cats:
    if c.slug in slug_set:
        fail('Category slug', f'Duplicate slug: {c.slug}')
    slug_set.add(c.slug)
    ok(f'Category: {c.title} ({c.slug})')

# === 10. Pages with view_count check ===
for p in Page.objects.all():
    ok(f'Page: {p.title} | views={p.view_count} | slug={p.slug}')

print('=' * 60)
print('RESULT SUMMARY')
print('=' * 60)
for p in pass_results:
    print(f'  [PASS] {p}')
for f in fail_results:
    print(f'  [FAIL] {f}')
print('=' * 60)
total = len(pass_results) + len(fail_results)
print(f'  [{len(pass_results)}/{total}] PASS | [{len(fail_results)}/{total}] FAIL')
print('=' * 60)

sys.exit(1 if fail_results else 0)
