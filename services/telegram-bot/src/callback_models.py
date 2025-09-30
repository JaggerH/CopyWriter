"""
回调数据模型定义
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional
from enum import Enum


class CallbackMessageType(Enum):
    """回调消息类型"""
    TASK_CREATED = "task_created"
    TASK_UPDATE = "task_update"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_TITLE_UPDATED = "task_title_updated"


class TelegramCallbackData(BaseModel):
    """Telegram 回调数据"""
    chat_id: str
    user_id: Optional[str] = None
    message_id: Optional[str] = None
    message_type: CallbackMessageType
    task_id: str
    task_data: Dict[str, Any]


class CallbackResponse(BaseModel):
    """回调响应"""
    success: bool
    message: str
    telegram_message_id: Optional[str] = None