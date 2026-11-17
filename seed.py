"""Скрипт для добавления демо-данных"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')
django.setup()

from pages.models import Page, PageCategory, SiteSetting, PageBlock
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

print('=== Запуск seed-скрипта ===')

# Создаём администратора (get_or_create)
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}
)
if created:
    admin.set_password('admin123')  # Для продакшена ОЧЕНЬ важно сменить пароль!
    admin.save()
    print('  ✓ Администратор создан (admin / admin123)')
else:
    print('  admin уже существует')

# Фикс для Page.objects.create() — требуется author
# Проверяем, есть ли published_at
now = timezone.now()

# Создаём категории
cats = [
    ('news', 'Новости', 'Последние новости и обновления', True),
    ('about', 'О нас', 'Информация о проекте', True),
    ('services', 'Услуги', 'Перечень услуг', True),
    ('faq', 'FAQ', 'Часто задаваемые вопросы', True),
    ('contacts', 'Контакты', 'Контактная информация', True),
]

for slug, title, desc, is_active in cats:
    PageCategory.objects.get_or_create(
        slug=slug,
        defaults={'title': title, 'description': desc, 'is_active': is_active}
    )
print('  ✓ Категории созданы/обновлены')

news = PageCategory.objects.get(slug='news')
services = PageCategory.objects.get(slug='services')

pages = [
    {
        'title': 'Welcome to DynamicPages!',
        'slug': 'welcome-dynamicpages',
        'excerpt': 'Our project is launched! Learn more about the platform capabilities.',
        'content': '<h2>What is DynamicPages?</h2><p>DynamicPages is a modern content management platform built with Django and PostgreSQL.</p><h3>Key Features:</h3><ul><li>Dynamic pages with admin panel</li><li>Categories and tags</li><li>SEO optimization</li><li>CKEditor visual editor</li><li>Responsive design</li></ul>',
        'category': news,
        'status': 'published',
        'is_featured': True,
    },
    {
        'title': 'How to Get Started',
        'slug': 'how-to-start',
        'excerpt': 'A step-by-step guide to setting up and using DynamicPages.',
        'content': '<h2>Step-by-Step Guide</h2><h3>Step 1: Register</h3><p>Create your account in the system.</p><h3>Step 2: Create Page</h3><p>Go to admin panel and create a new page.</p><h3>Step 3: Publish</h3><p>Fill in content, add images, and publish!</p>',
        'category': services,
        'status': 'published',
        'is_featured': True,
    },
    {
        'title': 'Our Services and Features',
        'slug': 'our-services',
        'excerpt': 'Full list of services we provide to our clients.',
        'content': '<h2>Our Services</h2><ol><li>Website Development</li><li>SEO Optimization</li><li>Administration</li><li>Consulting</li></ol><p>Contact us for details!</p>',
        'category': services,
        'status': 'published',
        'is_featured': True,
    },
    {
        'title': 'About DynamicPages Project',
        'slug': 'about-project',
        'excerpt': 'History, team, and mission of our project.',
        'content': '<h2>Our History</h2><p>DynamicPages was created in 2024 to simplify dynamic content management.</p><h2>Our Team</h2><p>We are a team of experienced developers, designers, and digital marketing experts.</p><h2>Our Mission</h2><p>To make content management accessible and convenient for everyone.</p>',
        'category': PageCategory.objects.get(slug='about'),
        'status': 'published',
        'is_featured': False,
    },
    {
        'title': 'FAQ - Frequently Asked Questions',
        'slug': 'faq-general',
        'excerpt': 'Answers to the most popular questions about our project.',
        'content': '<h2>Frequently Asked Questions</h2><h3>How to create a page?</h3><p>Log in to admin panel and click "Create Page".</p><h3>Can I use PostgreSQL?</h3><p>Yes! Django fully supports PostgreSQL.</p><h3>Does it support mobile devices?</h3><p>Yes, responsive design works on all devices.</p>',
        'category': PageCategory.objects.get(slug='faq'),
        'status': 'published',
        'is_featured': False,
    },
    {
        'title': 'Contact Information',
        'slug': 'contact-info',
        'excerpt': 'Reach us by any convenient way.',
        'content': '<h2>How to contact us</h2><p><strong>Email:</strong> info@example.com</p><p><strong>Phone:</strong> +7 (999) 123-45-67</p><p><strong>Address:</strong> Bangkok, Thailand</p><p><strong>Office Hours:</strong> Mon-Fri, 9:00 - 18:00</p>',
        'category': PageCategory.objects.get(slug='contacts'),
        'status': 'published',
        'is_featured': False,
    },
]

for idx, p in enumerate(pages):
    Page.objects.get_or_create(
        slug=p['slug'],
        defaults={
            **p,
            'author': admin,
            'published_at': now - datetime.timedelta(days=(6 - idx)),
        }
    )
print('  ✓ Демо-страницы созданы/обновлены')

# === Создаём SiteSetting, если их ещё нет ===
site_settings_data = {
    'site_title': {'key': 'site_title', 'label': 'Название сайта', 'value': 'DynamicPages'},
    'site_description': {'key': 'site_description', 'label': 'Описание сайта', 'value': 'Современный CMS на Django с PostgreSQL'},
    'site_email': {'key': 'site_email', 'label': 'Email сайта', 'value': 'info@example.com'},
    'site_phone': {'key': 'site_phone', 'label': 'Телефон сайта', 'value': '+7 (999) 123-45-67'},
    'site_address': {'key': 'site_address', 'label': 'Адрес сайта', 'value': 'Bangkok, Thailand'},
    'facebook_url': {'key': 'facebook_url', 'label': 'Facebook', 'value': 'https://facebook.com/dynamicpages'},
    'instagram_url': {'key': 'instagram_url', 'label': 'Instagram', 'value': 'https://instagram.com/dynamicpages'},
    'analytics_id': {'key': 'analytics_id', 'label': 'ID аналитики', 'value': ''},
}

for label, data in site_settings_data.items():
    obj, created = SiteSetting.objects.get_or_create(
        key=data['key'],
        defaults={
            'label': data['label'],
            'value': data['value'],
        }
    )
    if created:
        print(f'  ✓ SiteSetting "{label}" создан')
    else:
        obj.value = data['value']
        obj.label = data['label']
        obj.save()
        print(f'  ✓ SiteSetting "{label}" обновлён')

print(f'  SiteSetting: {SiteSetting.objects.count()}')

# === Создаём PageBlock демо-блоки для первых 3 страниц ===
demo_blocks = [
    {
        'title': 'Дополнительное описание',
        'content': '<p>Это демо-блок для демонстрации возможности добавлять динамические блоки контента на страницы.</p>',
        'page_slug': 'welcome-dynamicpages',
    },
    {
        'title': 'Наши преимущества',
        'content': '<h3>Почему выбирают нас?</h3><ul><li>Современные технологии</li><li>Простота использования</li><li>Масштабируемость</li><li>Поддержка 24/7</li></ul>',
        'page_slug': 'how-to-start',
    },
    {
        'title': 'Отзывы клиентов',
        'content': '<blockquote>Отличный проект! Очень удобно управлять контентом.</blockquote><p>— Иван Петров, директор компании "TechCorp"</p>',
        'page_slug': 'contact-info',
    },
]

for block_data in demo_blocks:
    page = Page.objects.get(slug=block_data['page_slug'])
    PageBlock.objects.get_or_create(
        page=page,
        title=block_data['title'],
        defaults={
            'content': block_data['content'],
            'ordering': PageBlock.objects.filter(page=page).count(),
        }
    )

print(f'  ✓ PageBlock демо-блоки созданы. Всего блоков: {PageBlock.objects.count()}')

print('\n=== Seed-скрипт завершён ===')
print(f'Категории: {PageCategory.objects.count()}')
print(f'Страницы опубликованы: {Page.objects.filter(status=Page.PUBLISHED).count()}')
print(f'PageBlocks: {PageBlock.objects.count()}')
