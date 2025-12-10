"""
Orchestrator API Client
"""
import httpx
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

from .config import OrchestratorConfig

logger = logging.getLogger(__name__)


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    url: str
    title: Optional[str] = None
    quality: str = "4"
    with_watermark: bool = False
    notification: Optional[Dict[str, Any]] = None


class CreateTaskResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    status: str
    message: str
    title: str
    platform: str  # douyin, tiktok, bilibili
    content_type: str  # video, image


class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    task_id: str
    title: str
    status: str
    current_step: str
    progress: int
    url: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OrchestratorClient:
    """Orchestrator服务客户端"""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.base_url = config.base_url
        self.timeout = config.timeout
    
    async def create_task(self, url: str, chat_id: str, user_id: str, 
                         message_id: str, title: Optional[str] = None) -> Optional[CreateTaskResponse]:
        """创建新任务"""
        try:
            # 构建通知配置
            notification_config = {
                "callback_type": "telegram",
                "chat_id": chat_id,
                "user_id": user_id,
                "message_id": message_id
            }
            
            request_data = CreateTaskRequest(
                url=url,
                title=title,
                notification=notification_config
            )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/process-media",  # 🆕 使用新的统一接口
                    json=request_data.dict()
                )

                if response.status_code == 200:
                    data = response.json()
                    return CreateTaskResponse(**data)
                else:
                    logger.error(f"Failed to create task: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None
    
    async def get_task_detail(self, task_id: str) -> Optional[TaskDetailResponse]:
        """获取任务详情"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tasks/{task_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    return TaskDetailResponse(**data)
                else:
                    logger.error(f"Failed to get task detail: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting task detail: {e}")
            return None
    
    async def health_check(self) -> bool:
        """检查orchestrator服务健康状态"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False