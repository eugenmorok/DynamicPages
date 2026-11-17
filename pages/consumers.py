"""
WebSocket consumers (Django Channels) — real-time обновления.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from asgiref.sync import sync_to_async

from .models import Comment, Page


User = get_user_model()


@database_sync_to_async
def _get_user(token):
    """Simple token-based lookup for unauthenticated deployments."""
    from django.contrib.sessions.backends.db import SessionStore
    try:
        session = SessionStore(token)
        session.load()
        user_id = session.get('_auth_user_id')
        if user_id:
            return User.objects.get(pk=user_id)
    except Exception:
        pass
    return None


class CommentWebSocketConsumer(AsyncWebsocketConsumer):
    """Real-time comment feed — broadcast new approved comments."""
    
    async def connect(self):
        self.room_name = 'comments'
        self.room_group_name = f'channel_layer_{self.room_name}'
        
        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
    
    async def send_comment(self, event):
        """Receive comment event from broadcast and send to client."""
        data = event['comment']
        await self.send(text_data=json.dumps({
            'type': 'new_comment',
            'comment': data,
        }))


class PageActivityConsumer(AsyncWebsocketConsumer):
    """Page activity feed — view counts, page updates."""
    
    async def connect(self):
        page_slug = self.scope['url_route']['kwargs'].get('slug')
        if page_slug:
            self.room_name = f'activity:{page_slug}'
        else:
            self.room_name = 'activity:all'
        
        self.room_group_name = f'channel_layer_{self.room_name}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        
        # Send cached view count as initial state
        cached_count = cache.get(f'page_view:{self.room_name}')
        await self.send(text_data=json.dumps({
            'type': 'init',
            'view_count': cached_count or 0,
        }))
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


class AdminNotificationConsumer(AsyncWebsocketConsumer):
    """Admin notification feed — protected by authentication."""
    
    async def connect(self):
        # Require authentication
        token = self.scope.get('query_string', b'').decode()
        if not token:
            await self.close(code=4001)
            return
        
        user = await _get_user(token)
        if not user or not user.is_staff:
            await self.close(code=4003)
            return
        
        self.room_name = 'admin_notifications'
        self.room_group_name = f'channel_layer_{self.room_name}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
    
    async def send_notification(self, event):
        """Receive notification event and forward to client."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
            'timestamp': event['timestamp'],
        }))


# ============================================================
# URL routing for WebSocket consumers
# ============================================================
from django.urls import path
from .consumers import (
    CommentWebSocketConsumer,
    PageActivityConsumer,
    AdminNotificationConsumer,
)

websocket_urlpatterns = [
    path('ws/comments/', CommentWebSocketConsumer.as_asgi()),
    path('ws/page-activity/<slug:slug>/', PageActivityConsumer.as_asgi()),
    path('ws/admin/notifications/', AdminNotificationConsumer.as_asgi()),
]
