"""
通用通知管理器
支持 WebSocket、Telegram、Notion 等多种回调方式
"""
import asyncio
import logging
import json
import httpx
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod

from models import CallbackType, NotificationConfig, NotificationMessage

logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """通知提供者抽象基类"""
    
    @abstractmethod
    async def send_notification(self, message: NotificationMessage) -> bool:
        """发送通知"""
        pass
    
    @abstractmethod
    def get_provider_type(self) -> CallbackType:
        """获取提供者类型"""
        pass


class WebSocketProvider(NotificationProvider):
    """WebSocket 通知提供者"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    async def send_notification(self, message: NotificationMessage) -> bool:
        try:
            websocket_message = {
                "type": message.message_type,
                "task_id": message.task_id,
                "data": message.data
            }
            await self.connection_manager.broadcast(websocket_message)
            logger.info(f"WebSocket notification sent for task {message.task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
            return False
    
    def get_provider_type(self) -> CallbackType:
        return CallbackType.WEBSOCKET


class TelegramProvider(NotificationProvider):
    """Telegram 通知提供者 - 通过 HTTP 回调"""
    
    def __init__(self, telegram_bot_service_url: str):
        self.telegram_bot_service_url = telegram_bot_service_url.rstrip('/')
    
    async def send_notification(self, message: NotificationMessage) -> bool:
        if not message.notification_config or not message.notification_config.chat_id:
            logger.warning(f"Missing chat_id for Telegram notification: {message.task_id}")
            return False
        
        try:
            # 构建回调数据
            callback_data = {
                "chat_id": message.notification_config.chat_id,
                "user_id": message.notification_config.user_id,
                "message_id": message.notification_config.message_id,
                "message_type": message.message_type,
                "task_id": message.task_id,
                "task_data": message.data
            }
            
            # 选择合适的端点
            endpoint_map = {
                "task_created": "/api/callback/task_created",
                "task_update": "/api/callback/task_update", 
                "task_completed": "/api/callback/task_completed",
                "task_failed": "/api/callback/task_failed",
                "task_title_updated": "/api/callback/task_title_updated"
            }
            
            endpoint = endpoint_map.get(message.message_type, "/api/callback")
            url = f"{self.telegram_bot_service_url}{endpoint}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=callback_data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info(f"Telegram callback sent successfully for task {message.task_id}")
                        return True
                    else:
                        logger.warning(f"Telegram callback failed: {result.get('message', 'Unknown error')}")
                        return False
                else:
                    logger.error(f"Telegram callback HTTP error: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Telegram callback timeout for task {message.task_id}")
            return False
        except httpx.ConnectError:
            logger.error(f"Cannot connect to telegram-bot service at {self.telegram_bot_service_url}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram callback: {e}")
            return False
    
    def get_provider_type(self) -> CallbackType:
        return CallbackType.TELEGRAM


class NotionProvider(NotificationProvider):
    """Notion 通知提供者（未来实现）"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def send_notification(self, message: NotificationMessage) -> bool:
        # TODO: 实现 Notion 集成
        logger.info(f"Notion notification for task {message.task_id} (not implemented)")
        return True
    
    def get_provider_type(self) -> CallbackType:
        return CallbackType.NOTION


class UnifiedNotificationManager:
    """统一通知管理器"""
    
    def __init__(self, connection_manager=None):
        self.providers: Dict[CallbackType, NotificationProvider] = {}
        
        # 初始化 WebSocket 提供者
        if connection_manager:
            self.providers[CallbackType.WEBSOCKET] = WebSocketProvider(connection_manager)
        
        # 初始化 Telegram 提供者（HTTP 回调）
        telegram_bot_url = os.getenv("TELEGRAM_BOT_SERVICE_URL", "http://telegram-bot:8000")
        try:
            self.providers[CallbackType.TELEGRAM] = TelegramProvider(telegram_bot_url)
            logger.info(f"Telegram notification provider initialized (callback URL: {telegram_bot_url})")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram provider: {e}")
        
        # 初始化 Notion 提供者（如果配置了）
        notion_key = os.getenv("NOTION_API_KEY")
        if notion_key:
            self.providers[CallbackType.NOTION] = NotionProvider(notion_key)
            logger.info("Notion notification provider initialized")
    
    async def send_notification(self, message_type: str, task_id: str, data: dict, 
                               notification_config: Optional[NotificationConfig] = None):
        """发送通知到所有适用的提供者"""
        # 始终发送 WebSocket 通知（向后兼容）
        if CallbackType.WEBSOCKET in self.providers:
            websocket_message = NotificationMessage(
                callback_type=CallbackType.WEBSOCKET,
                task_id=task_id,
                message_type=message_type,
                data=data
            )
            await self.providers[CallbackType.WEBSOCKET].send_notification(websocket_message)
        
        # 如果指定了特定的通知配置，发送对应通知
        if notification_config:
            provider = self.providers.get(notification_config.callback_type)
            if provider:
                message = NotificationMessage(
                    callback_type=notification_config.callback_type,
                    task_id=task_id,
                    message_type=message_type,
                    data=data,
                    notification_config=notification_config
                )
                await provider.send_notification(message)
            else:
                logger.info(f"Provider not available for callback type: {notification_config.callback_type}, skipping notification")
    
    async def notify_task_created(self, task_id: str, data: dict, 
                                 notification_config: Optional[NotificationConfig] = None):
        """通知任务已创建"""
        await self.send_notification("task_created", task_id, data, notification_config)
    
    async def notify_task_update(self, task_id: str, data: dict, 
                                notification_config: Optional[NotificationConfig] = None):
        """通知任务状态更新"""
        await self.send_notification("task_update", task_id, data, notification_config)
    
    async def notify_task_completed(self, task_id: str, data: dict, 
                                   notification_config: Optional[NotificationConfig] = None):
        """通知任务完成"""
        await self.send_notification("task_completed", task_id, data, notification_config)
    
    async def notify_task_failed(self, task_id: str, data: dict, 
                                notification_config: Optional[NotificationConfig] = None):
        """通知任务失败"""
        await self.send_notification("task_failed", task_id, data, notification_config)
    
    async def notify_task_deleted(self, task_id: str, data: dict):
        """通知任务删除（只发送 WebSocket）"""
        await self.send_notification("task_deleted", task_id, data, None)