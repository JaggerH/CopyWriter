from pydantic import BaseModel
from typing import Optional, Dict, List, Union
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"

class CallbackType(Enum):
    WEBSOCKET = "websocket"
    TELEGRAM = "telegram"
    WECOM = "wecom"
    NOTION = "notion"

class NotificationConfig(BaseModel):
    """Configuration for task completion notifications"""
    callback_type: CallbackType
    # For Telegram callbacks
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    message_id: Optional[str] = None
    # For WeChat callbacks
    wecom_user_id: Optional[str] = None
    wecom_agent_id: Optional[str] = None
    # For future Notion callbacks
    notion_page_id: Optional[str] = None
    # Generic callback data
    callback_data: Optional[Dict] = None

class TaskInfo(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    current_step: str
    progress: int
    created_time: datetime
    updated_time: datetime
    url: str
    chat_id: Optional[str] = None  # Kept for backward compatibility
    notification: Optional[NotificationConfig] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

class TaskListItem(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    created_time: datetime
    progress: int

class TaskDetailResponse(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    current_step: str
    progress: int
    created_time: datetime
    updated_time: datetime
    url: str
    # Processing result (only text content)
    result: Optional[Dict] = None
    error: Optional[str] = None

class CreateTaskRequest(BaseModel):
    url: str
    title: Optional[str] = None
    quality: Optional[str] = "4"
    with_watermark: Optional[bool] = False
    # Notification configuration
    notification: Optional[NotificationConfig] = None

class CreateTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    title: str

class TaskListResponse(BaseModel):
    tasks: List[TaskListItem]
    total: int
    page: int
    page_size: int

class WebSocketMessage(BaseModel):
    type: str  # "task_update", "task_created", "task_deleted"
    task_id: str
    data: Dict

class NotificationMessage(BaseModel):
    """Generic notification message for different callback types"""
    callback_type: CallbackType
    task_id: str
    message_type: str  # "task_created", "task_update", "task_completed", "task_failed"
    data: Dict
    notification_config: Optional[NotificationConfig] = None