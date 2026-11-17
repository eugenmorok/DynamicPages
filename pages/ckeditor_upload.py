"""
CKEditor Upload restrictions
Ограничивает тип и размер загружаемых файлов в CKEditor.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico'}
ALLOWED_MIME_TYPES = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'image/svg+xml', 'image/bmp', 'image/x-icon', 'image/tiff', 'image/x-ms-bmp',
]
# Для совместимости
ALLOWED_TYPES = ALLOWED_MIME_TYPES
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes


def _check_extension(filename):
    """Проверка расширения файла"""
    if not filename:
        return False
    _, ext = os.path.splitext(filename)
    return ext.lower().split('?')[0] in ALLOWED_EXTENSIONS


def _check_mime(content_type):
    """Проверка MIME-типа"""
    if not content_type:
        return False
    return content_type.startswith('image/') and content_type in ALLOWED_MIME_TYPES


def ckeditor_upload(request):
    """
    Кастомная точка загрузки для CKEditor 
    с ограничениями по типу и размеру
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Неверный метод'}, status=400)
    
    uploaded = request.GET.get('CKEditorUploadCallback') or request.GET.get('CKEditorFuncNum')
    
    # Get the file
    file_obj = request.FILES.get('upload') or request.FILES.get('CKEditor', request.FILES.get('upload'))
    
    if not file_obj:
        if uploaded:
            return JsonResponse({
                'uploaded': 0,
                'error': {'message': 'Файл не найден'},
                'CKEditorFuncNum': uploaded
            })
        return JsonResponse({'error': 'Файл не найден'}, status=400)
    
    # Проверка размера
    if file_obj.size > MAX_FILE_SIZE:
        if uploaded:
            return JsonResponse({
                'uploaded': 0,
                'error': {'message': 'Файл слишком большой. Максимум 10MB'},
                'CKEditorFuncNum': uploaded
            })
        return JsonResponse({'error': 'Файл слишком большой. Максимум 10MB'}, status=400)
    
    # Проверка MIME-типа
    content_type = file_obj.content_type
    if not _check_mime(content_type):
        if uploaded:
            return JsonResponse({
                'uploaded': 0,
                'error': {'message': f'Неподдерживаемый тип: {content_type or "unknown"}'},
                'CKEditorFuncNum': uploaded
            })
        return JsonResponse({'error': f'Неподдерживаемый тип: {content_type or "unknown"}, только изображения'}, status=400)
    
    # Проверка расширения как дополнительной защиты
    filename = getattr(file_obj, 'name', 'file')
    if not _check_extension(filename):
        if uploaded:
            return JsonResponse({
                'uploaded': 0,
                'error': {'message': 'Запрещённое расширение файла'},
                'CKEditorFuncNum': uploaded
            })
        return JsonResponse({'error': 'Запрещённое расширение файла'}, status=400)
    
    # Сохранение файла
    from django.core.files.storage import DefaultStorage
    from ckeditor_uploader.utils import get_ckeditorupload_urlpatterns, smart_path
    from django.utils.text import get_valid_filename
    import uuid
    
    upload_to = getattr(settings, 'CKEDITOR_UPLOAD_PATH', 'uploads/')
    # Создаем уникальный путь
    ext = os.path.splitext(filename)[1] or '.jpg'  # fallback to .jpg
    filename = get_valid_filename(filename.rsplit('.', 1)[0])
    unique_name = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(upload_to, unique_name)
    
    storage = DefaultStorage()
    storage.save(full_path, file_obj)
    
    # Build URL
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    url = f"{media_url.rstrip('/')}/{full_path.lstrip('/')}"
    
    if uploaded:
        return JsonResponse({
            'uploaded': 1,
            'fileName': unique_name,
            'url': url,
            'CKEditorFuncNum': uploaded,
        })
    
    return JsonResponse({
        'uploaded': 1,
        'fileName': unique_name,
        'url': url,
    })
