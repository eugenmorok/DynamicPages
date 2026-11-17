"""
WebSocket consumers для Django Channels.
Реализация real-time уведомлений для комментариев.
"""
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class CommentWebSocketConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer для комментариев."""
    
    async def connect(self):
        self.room_group_name = 'comments'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send welcome message
        await self.send_json({
            'type': 'welcome',
            'message': 'Connected to comment real-time feed',
        })
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    # Receive message from JavaScript
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', '')
        
        if message_type == 'subscribe_page':
            page_pk = data.get('page_id')
            if page_pk:
                room = f'comments_page_{page_pk}'
                await self.channel_layer.group_add(room, self.channel_name)
                await self.send_json({
                    'type': 'subscribed',
                    'page_id': page_pk,
                })
        
        elif message_type == 'unsubscribe_page':
            page_pk = data.get('page_id')
            if page_pk:
                room = f'comments_page_{page_pk}'
                await self.channel_layer.group_discard(room, self.channel_name)
    
    # Receive message from group
    async def new_comment(self, event):
        """Отправка нового комментария через WebSocket."""
        await self.send_json({
            'type': 'new_comment',
            'comment': event['comment'],
        })
    
    async def comment_reply(self, event):
        """Отправка ответа на комментарий через WebSocket."""
        await self.send_json({
            'type': 'comment_reply',
            'comment': event['comment'],
        })
    
    async def comment_updated(self, event):
        """Отправка обновления комментария через WebSocket."""
        await self.send_json({
            'type': 'comment_updated',
            'comment': event['comment'],
        })


class PageActivityConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer для активности страниц."""
    
    async def connect(self):
        self.room_group_name = 'page_activity'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )


class AdminNotificationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer для админ-уведомлений."""
    
    async def connect(self):
        # Require authentication
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        self.room_group_name = f'admin_{self.scope["user"].pk}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )


# ==================== WebSocket URL Configuration ====================

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/comments/', CommentWebSocketConsumer.as_asgi()),
    path('ws/page-activity/', PageActivityConsumer.as_asgi()),
    path('ws/admin/notifications/', AdminNotificationConsumer.as_asgi()),
]
