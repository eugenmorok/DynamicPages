"""Тестовая проверка всех маршрутов проекта DynamicPages."""

import sys
import http.client
from urllib.parse import urlparse

PASS = 0
FAIL = 0

def test_route(name, path, expected=200):
    global PASS, FAIL
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        if resp.status == expected:
            PASS += 1
            return f"[PASS] {name} -> {resp.status} | {len(body):,d} bytes"
        else:
            FAIL += 1
            return f"[FAIL] {name} -> {resp.status} (expected {expected}) | {len(body):,d} bytes"
    except Exception as e:
        FAIL += 1
        return f"[FAIL] {name} -> ERR: {e}"

def test_route_post(name, path):
    global PASS, FAIL
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
        conn.request("POST", path)
        resp = conn.getresponse()
        resp.read()
        if resp.status == 302:
            PASS += 1
            return f"[PASS] {name} -> POST {resp.status} (redirect)"
        else:
            FAIL += 1
            return f"[FAIL] {name} -> POST {resp.status} (expected 302)"
    except Exception as e:
        FAIL += 1
        return f"[FAIL] {name} -> POST ERR: {e}"

# === Секция 1: Главная и страницы ===
lines = []
lines.append("=" * 60)
lines.append("  1. ГЛАВНАЯ И СТРАНИЦЫ")
lines.append("=" * 60)
lines.append(test_route("Home", "/"))
lines.append(test_route("Pages listing", "/pages/"))

for slug in [
    "welcome-dynamicpages", "how-to-start", "our-services",
    "about-project", "faq-general", "contact-info"
]:
    lines.append(test_route(f"Page: {slug}", f"/page/{slug}/"))

# === Секция 2: Категории ===
lines.append("")
lines.append("=" * 60)
lines.append("  2. КАТЕГОРИИ")
lines.append("=" * 60)
for cat in ["news", "about", "services", "faq", "contacts"]:
    lines.append(test_route(f"Category: {cat}", f"/category/{cat}/"))

# === Секция 3: Поиск ===
lines.append("")
lines.append("=" * 60)
lines.append("  3. ПОИСК")
lines.append("=" * 60)
lines.append(test_route("Search: django", "/pages/?q=django"))
lines.append(test_route("Search: services", "/pages/?q=services"))
lines.append(test_route("Search: nothing", "/pages/?q=zzzznotfoundzzz"))

# === Секция 4: 404 ===
lines.append("")
lines.append("=" * 60)
lines.append("  4. ОШИБКИ (должны быть 404)")
lines.append("=" * 60)
lines.append(test_route("Page not found", "/page/non-existent-page-xyz/", 404))
lines.append(test_route("Category not found", "/category/non-existent-cat/", 404))

# === Секция 5: CRUD маршруты ===
lines.append("")
lines.append("=" * 60)
lines.append("  5. CRUD МАРШРУТЫ")
lines.append("=" * 60)
lines.append(test_route("Create page", "/create/"))
lines.append(test_route("Edit page", "/pages/welcome-dynamicpages/edit/"))
lines.append(test_route("Delete page", "/pages/welcome-dynamicpages/delete/"))
lines.append(test_route("Create category", "/categories/create/"))

# === Секция 6: Авторизация ===
lines.append("")
lines.append("=" * 60)
lines.append("  6. АВТОРИЗАЦИЯ")
lines.append("=" * 60)
lines.append(test_route("Login page", "/accounts/login/"))
lines.append(test_route("Logout page", "/accounts/logout/"))
lines.append(test_route("Reset password", "/accounts/password_reset/"))
lines.append(test_route("Admin", "/admin/"))
lines.append(test_route("API health", "/api/health/"))

# Сводка
lines.append("")
lines.append("=" * 60)
lines.append("  ИТОГО")
lines.append("=" * 60)
total = PASS + FAIL
lines.append(f"[RESULT] Passed: {PASS}/{total}  |  Failed: {FAIL}/{total}")
lines.append("=" * 60)

print("\n".join(lines))
sys.exit(1 if FAIL > 0 else 0)
