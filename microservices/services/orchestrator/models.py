from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskInfo(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    current_step: str
    progress: int
    created_time: datetime
    updated_time: datetime
    url: str
    chat_id: Optional[str] = None
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