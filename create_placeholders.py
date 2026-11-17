import os
import io
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')
django.setup()

from pages.models import Page, MediaGallery
from django.core.files.base import ContentFile
from PIL import Image

# Create directories
base = os.path.dirname(__file__)
media_path = base
for sub in ['uploads', 'uploads/images', 'pages', 'gallery']:
    path = os.path.join(media_path, sub)
    os.makedirs(path, exist_ok=True)
    print(f'Created: {os.path.join(media_path, sub)}')

# Generate placeholder green image
def make_placeholder_img(w=400, h=250):
    img = Image.new('RGB', (w, h), color=(75, 150, 75))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return buf

# Create placeholder colored image
def make_colored_img(color=(75, 150, 75), w=400, h=250):
    img = Image.new('RGB', (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return buf

# Get all pages
pages = Page.objects.all()
print(f'\nUpdating {pages.count()} pages with placeholder images')

colors = [
    (75, 150, 75),  # green
    (75, 100, 150), # blue
    (150, 100, 75), # orange
    (150, 75, 75),  # red
    (75, 150, 150), # teal
    (150, 150, 75), # yellow
]
i = 0
for page in pages:
    if not page.featured_image or not page.featured_image.name:
        buf = make_colored_img(colors[i % len(colors)])
        img_name = f'pages/{page.created_at.strftime("%Y/%m/%d")}/{page.slug}.jpg'
        page.featured_image.save(img_name, ContentFile(buf.read()), save=True)
        print(f'  Created: {page.title} -> {img_name}')
        i += 1

# Create default gallery items
if MediaGallery.objects.count() == 0:
    gallery_data = [
        ('Mountain View', 'Beautiful mountain landscape', (50, 130, 70)),
        ('Ocean Sunset', 'Stunning ocean sunset', (180, 100, 50)),
        ('City Night', 'City lights at night', (40, 40, 120)),
    ]
    for title, desc, color in gallery_data:
        buf = make_colored_img(color)
        gallery, created = MediaGallery.objects.get_or_create(
            title=title,
            defaults={'description': desc, 'is_active': True}
        )
        if created:
            gallery.image.save(f'{title.lower().replace(" ", "_")}.jpg', ContentFile(buf.read()), save=True)
            print(f'Created gallery: {title}')

print('\nDone! Refresh http://127.0.0.1:8080/')
