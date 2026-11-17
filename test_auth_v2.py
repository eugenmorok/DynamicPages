"""Auth + CRUD test via Django TestClient (proper session/CSRF handling)."""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')
import django; django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from pages.models import Page, PageCategory, PageBlock, SiteSetting
from django.test import Client

tc = Client()

results = []

def ok(name):
    results.append((name, True))

def fail(name, detail):
    results.append((f'{name}: {detail}', False))

# === AUTH ===

# Ensure test user
u, created = User.objects.get_or_create(
    username='authtest',
    defaults={'email': 'test@test.com', 'is_staff': True, 'is_superuser': True}
)
if created:
    u.set_password('authtest123')
    u.save()

# Login
logged_in = tc.login(username='authtest', password='authtest123')
if logged_in:
    ok('Login via Django TestClient: SUCCESS')
else:
    fail('Login via TestClient', 'FAILED')

# Check session after login
if tc.session.get('_auth_user_id'):
    ok('Session exists after login: True')
else:
    fail('Session check', 'No session after login')

# Test CRUD via authenticated client
# 1. Create Page
create_data = {
    'title': 'Created via Test',
    'slug': 'created-via-test',
    'content': '<p>Test content</p>',
    'excerpt': 'Page created by auth test script',
    'status': Page.PUBLISHED,
    'is_featured': False,
    'category': PageCategory.objects.first().pk,
}
r = tc.post('/create/', create_data)
if r.status_code in (302, 200):
    ok(f'Create page POST -> {r.status_code} ({"redirect" if r.status_code == 302 else "rendered"})')
else:
    fail('Create page POST', f'{r.status_code}')

# Verify page was created
if Page.objects.filter(slug='created-via-test').exists():
    ok('Page created successfully: created-via-test exists')
else:
    fail('Page creation verification', 'Page not found in DB')

# 2. Read the page
pages = Page.objects.filter(slug='created-via-test')
if pages:
    p = pages[0]
    r2 = tc.get('/page/created-via-test/')
    if r2.status_code == 200:
        ok(f'Detail page: {r2.status_code} ({len(r2.content)}b)')
    else:
        fail('Detail page', f'{r2.status_code}')
    
    # 3. Update
    update_data = create_data.copy()
    update_data['title'] = 'Updated via Test'
    r3 = tc.post(f'/pages/created-via-test/edit/', update_data)
    if r3.status_code in (302, 200):
        ok(f'Update page -> {r3.status_code}')
    else:
        fail('Update page', f'{r3.status_code}')
    
    # Verify update
    if Page.objects.filter(slug='created-via-test', title='Updated via Test').exists():
        ok('Page title updated: "Updated via Test"')
    else:
        fail('Update verification', 'Title not updated')
    
    # 4. Delete
    r4 = tc.post(f'/pages/created-via-test/delete/')
    if r4.status_code in (302, 200):
        ok(f'Delete page confirmation -> {r4.status_code}')
    else:
        fail('Delete page confirm', f'{r4.status_code}')

# 5. Logout
r5 = tc.get('/accounts/logout/')
if r5.status_code == 405:
    ok('Logout GET -> 405 (POST only — защитa от CSRF)')
else:
    fail('Logout GET', f'{r5.status_code}, expected 405')

# 6. Unauthenticated tries
unauth = Client()
for url, expected in [('/admin/', [302]), ('/create/', [302]), ('/pages/test/edit/', [302])]:
    r = unauth.get(url)
    if r.status_code in expected:
        ok(f'Unauth {url} -> {r.status_code} (redirect to login)')
    else:
        fail(f'Unauth {url}', f'{r.status_code}, expected {expected}')

# 7. PageBlock creation test
if Page.objects.filter(status=Page.PUBLISHED):
    test_page = Page.objects.filter(status=Page.PUBLISHED).first()
    block_count = PageBlock.objects.filter(page=test_page).count()
    ok(f'Current PageBlocks for {test_page.title}: {block_count}')

# === SUMMARY ===
passed = sum(1 for _, ok_val in results if ok_val)
failed = sum(1 for _, ok_val in results if not ok_val)

print('=' * 72)
for result, ok_val in results:
    marker = '[PASS]' if ok_val else '[FAIL]'
    print(f'  {marker} {result}')
print('=' * 72)
print(f'  RESULT: {passed} PASS | {failed} FAIL | {passed + failed} TOTAL')
print('=' * 72)

sys.exit(1 if failed else 0)
