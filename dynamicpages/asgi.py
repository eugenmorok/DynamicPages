"""
ASGI entry-point для WebSocket поддержки.
Использует Channels для WebSocket и стандартное ASGI для HTTP.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')

application = get_asgi_application()

# WebSocket routing (optional — only if Channels installed)
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from pages import consumers  # noqa: F401 — register consumers
    
    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': URLRouter(consumers.websocket_urlpatterns),
    })
except ImportError:
    # Channels not installed — standard ASGI only
    pass
