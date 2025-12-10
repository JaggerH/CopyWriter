from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx
import uuid
import os
import logging
import asyncio
import subprocess
from typing import Optional, Dict, List
import redis.asyncio as redis
import json
from datetime import datetime
from urllib.parse import urlparse
import re
from models import (
    TaskInfo, TaskListItem, TaskDetailResponse, CreateTaskRequest, 
    CreateTaskResponse, TaskListResponse, WebSocketMessage, TaskStatus as TaskStatusEnum,
    NotificationConfig, CallbackType
)
from notification_manager import UnifiedNotificationManager
from url_parser import VideoURLParser

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CopyWriter 任务编排服务",
    description="统一API网关，协调各微服务完成视频处理任务",
    version="1.0.0"
)

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 环境变量配置
VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://video-service:80")
ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL", "http://asr-service:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")

# Redis连接
redis_client = None

# WebSocket连接管理
active_connections: List[WebSocket] = []

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# 延迟初始化通知管理器
notification_manager = None

def get_notification_manager():
    """获取通知管理器实例（延迟初始化）"""
    global notification_manager
    if notification_manager is None:
        notification_manager = UnifiedNotificationManager(connection_manager=manager)
    return notification_manager

# 初始化URL解析器
url_parser = VideoURLParser()

class ProcessMediaRequest(BaseModel):
    """统一媒体处理请求（支持视频和图片）"""
    url: str
    quality: Optional[str] = "4"
    with_watermark: Optional[bool] = False
    notification: Optional[NotificationConfig] = None

class ProcessMediaResponse(BaseModel):
    """统一媒体处理响应"""
    task_id: str
    status: str
    message: str
    title: str
    platform: str  # douyin, tiktok, bilibili
    content_type: str  # video, image
    result: Optional[Dict] = None

class DetectTypeResponse(BaseModel):
    """内容类型检测响应"""
    platform: str
    content_type: str
    aweme_type: int
    clean_url: str
    title: str

# Legacy - for backward compatibility (will be removed)
class ProcessVideoRequest(BaseModel):
    url: str
    chat_id: Optional[str] = None
    quality: Optional[str] = "4"
    with_watermark: Optional[bool] = False

class ProcessVideoResponse(BaseModel):
    task_id: str
    status: str
    message: str
    result: Optional[Dict] = None

# Legacy TaskStatus model for backward compatibility
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    current_step: str
    progress: int
    result: Optional[Dict] = None
    error: Optional[str] = None

# Utility functions
def extract_title_from_url_or_text(input_text: str) -> str:
    """从URL或文本中提取有意义的标题"""
    try:
        # 首先尝试用URL解析器生成标题
        title = url_parser.generate_task_title(input_text)
        if title and title != "视频任务":
            return title
        
        # 回退到原有逻辑
        parsed = urlparse(input_text)
        domain = parsed.netloc.lower()
        
        if 'bilibili.com' in domain or 'b23.tv' in domain:
            return f"Bilibili视频 - {input_text[-12:]}"
        elif 'douyin.com' in domain or 'iesdouyin.com' in domain:
            return f"抖音视频 - {input_text[-12:]}"
        elif 'tiktok.com' in domain:
            return f"TikTok视频 - {input_text[-12:]}"
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return f"YouTube视频 - {input_text[-12:]}"
        else:
            return f"视频任务 - {input_text[-12:]}"
    except:
        return f"视频任务 - {str(uuid.uuid4())[:8]}"

def get_clean_video_url(input_text: str) -> str:
    """从输入文本中获取清洁的视频URL"""
    try:
        # 尝试用URL解析器获取清洁URL
        clean_url = url_parser.get_clean_url(input_text)
        if clean_url:
            return clean_url

        # 如果没有找到支持的平台URL，返回原始输入（假设它就是URL）
        return input_text.strip()
    except:
        return input_text.strip()

async def detect_content_info(url: str) -> dict:
    """
    识别链接的平台和内容类型

    流程:
    1. 清理URL
    2. 调用 video-service 的 /api/hybrid/video_data 接口
    3. 解析平台 (douyin/tiktok/bilibili)
    4. 解析类型 (video/image)
    5. 返回完整识别结果

    Args:
        url: 原始URL或分享文本

    Returns:
        {
            "platform": "douyin" | "tiktok" | "bilibili" | "unknown",
            "content_type": "video" | "image",
            "aweme_type": int,  # 原始类型代码
            "clean_url": str,
            "title": str,
            "error": None | str
        }
    """
    try:
        # 步骤1: 清理URL
        clean_url = get_clean_video_url(url)
        logger.info(f"[ContentDetection] Analyzing URL: {clean_url}")

        # 步骤2: 调用 video-service 识别
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{VIDEO_SERVICE_URL}/api/hybrid/video_data",
                params={"url": clean_url, "minimal": "true"}
            )

            if response.status_code != 200:
                error_msg = f"Failed to detect type: HTTP {response.status_code}"
                logger.error(f"[ContentDetection] {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"无法识别链接类型: {error_msg}"
                )

            result = response.json()
            data = result.get('data', {})

            # 步骤3: 提取平台信息
            platform = data.get('platform', 'unknown')

            # 步骤4: 提取类型信息
            content_type = data.get('type', 'video')

            # 提取原始 aweme_type
            aweme_type = data.get('aweme_type', 0)

            # 提取标题
            title = data.get('desc', '') or extract_title_from_url_or_text(url)

            logger.info(
                f"[ContentDetection] ✓ Detected - "
                f"Platform: {platform}, "
                f"Type: {content_type}, "
                f"AwemeType: {aweme_type}, "
                f"Title: {title[:30]}..."
            )

            return {
                "platform": platform,
                "content_type": content_type,
                "aweme_type": aweme_type,
                "clean_url": clean_url,
                "title": title,
                "error": None
            }

    except httpx.TimeoutException as e:
        error_msg = f"请求超时: {str(e)}"
        logger.error(f"[ContentDetection] {error_msg}")
        raise HTTPException(status_code=504, detail=f"识别超时: {error_msg}")
    except httpx.ConnectError as e:
        error_msg = f"连接失败: {str(e)}"
        logger.error(f"[ContentDetection] {error_msg}")
        raise HTTPException(status_code=503, detail=f"无法连接到视频服务: {error_msg}")
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP错误: {e}"
        logger.error(f"[ContentDetection] {error_msg}")
        raise HTTPException(status_code=502, detail=f"视频服务错误: {error_msg}")
    except HTTPException:
        raise  # 重新抛出 HTTP 异常
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        logger.error(f"[ContentDetection] {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"无法识别链接类型: {error_msg}"
        )

# 保持向后兼容性的包装函数
async def notify_websocket_clients(message_type: str, task_id: str, data: dict):
    """Notify all WebSocket clients about task updates (Legacy function)"""
    manager = get_notification_manager()
    await manager.send_notification(message_type, task_id, data, None)

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查FFmpeg是否可用
        ffmpeg_status = "unhealthy"
        ffmpeg_version = "not found"
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                ffmpeg_status = "healthy"
                ffmpeg_version = result.stdout.split('\n')[0] if result.stdout else "Unknown"
        except:
            pass
        
        # 检查各服务状态
        async with httpx.AsyncClient() as client:
            services = {
                "video-service": f"{VIDEO_SERVICE_URL}/health",
                "asr-service": f"{ASR_SERVICE_URL}/health"
            }
            
            service_status = {}
            for name, url in services.items():
                try:
                    response = await client.get(url, timeout=5.0)
                    service_status[name] = "healthy" if response.status_code == 200 else "unhealthy"
                except:
                    service_status[name] = "unreachable"
        
        # 检查Redis连接
        try:
            r = await get_redis()
            await r.ping()
            service_status["redis"] = "healthy"
        except:
            service_status["redis"] = "unhealthy"
        
        service_status["ffmpeg"] = ffmpeg_status
        
        return {
            "status": "healthy",
            "service": "orchestrator-with-ffmpeg",
            "ffmpeg_version": ffmpeg_version,
            "services": service_status
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.websocket("/ws/tasks")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time task updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/tasks", response_model=CreateTaskResponse)
async def create_task(request: CreateTaskRequest, background_tasks: BackgroundTasks):
    """Create a new video processing task"""
    task_id = str(uuid.uuid4())
    created_time = datetime.now().isoformat()
    
    # 处理输入URL，支持从复杂文本中提取URL和标题
    clean_url = get_clean_video_url(request.url)
    title = request.title or extract_title_from_url_or_text(clean_url)
    # 记录URL解析信息
    video_links = url_parser.parse_video_links(clean_url)
    if video_links:
        logger.info(f"识别到{video_links[0].platform_name}链接: {clean_url}, 视频ID: {video_links[0].video_id}")
    
    # Save task to Redis with enhanced data
    r = await get_redis()
    task_data = {
        "task_id": task_id,
        "status": "queued",
        "current_step": "initialized",
        "progress": "0",
        "url": clean_url,  # 使用清洁后的URL
        "title": title,
        "created_time": created_time,
        "updated_time": created_time,
        "quality": request.quality,
        "with_watermark": str(request.with_watermark)
    }
    
    # 保存通知配置到 Redis
    if request.notification:
        task_data["notification_config"] = request.notification.json()
    
    await r.hset(f"task:{task_id}", mapping=task_data)
    await r.zadd("tasks:created", {task_id: datetime.now().timestamp()})
    
    # 创建一个使用清洁URL的ProcessVideoRequest对象传递给pipeline
    clean_request = ProcessVideoRequest(
        url=clean_url,
        quality=request.quality,
        with_watermark=request.with_watermark,
        chat_id=None  # 新任务API不使用chat_id
    )
    # Start processing
    background_tasks.add_task(process_video_pipeline, task_id, clean_request)
    
    # 发送创建通知
    notification_data = {
        "task_id": task_id,
        "title": title,
        "status": "queued",
        "created_time": created_time,
        "progress": 0,
        "url": clean_url
    }
    manager = get_notification_manager()
    await manager.notify_task_created(task_id, notification_data, request.notification)
    
    return CreateTaskResponse(
        task_id=task_id,
        status="queued",
        message="任务已创建，开始处理",
        title=title
    )

@app.post("/api/process-media", response_model=ProcessMediaResponse)
async def process_media(request: ProcessMediaRequest, background_tasks: BackgroundTasks):
    """
    处理媒体内容的统一入口（智能路由）

    支持的平台：
    - 抖音 (Douyin)
    - TikTok
    - Bilibili

    支持的类型：
    - 视频：下载 → 转码 → ASR 转录
    - 图片：下载图集

    流程：
    1. 识别平台和内容类型
    2. 创建任务
    3. 智能路由到对应的处理管道
    4. 返回任务信息
    """
    task_id = str(uuid.uuid4())
    r = await get_redis()
    created_time = datetime.now().isoformat()

    # 🔍 步骤1: 识别平台和内容类型
    content_info = await detect_content_info(request.url)

    platform = content_info['platform']
    content_type = content_info['content_type']
    clean_url = content_info['clean_url']
    title = content_info['title']

    # 序列化 notification 配置
    notification_config_json = None
    if request.notification:
        notification_config_json = request.notification.model_dump_json()

    # 📝 步骤2: 保存任务到 Redis
    await r.hset(f"task:{task_id}", mapping={
        "status": "queued",
        "current_step": "initialized",
        "progress": "0",
        "url": clean_url,
        "title": title,
        "platform": platform,  # 🆕 保存平台信息
        "content_type": content_type,  # 🆕 保存内容类型
        "aweme_type": str(content_info['aweme_type']),  # 🆕 保存原始类型
        "created_time": created_time,
        "updated_time": created_time,
        "notification_config": notification_config_json if notification_config_json else ""
    })

    # 创建清理后的请求对象
    clean_request = ProcessMediaRequest(
        url=clean_url,
        quality=request.quality,
        with_watermark=request.with_watermark,
        notification=request.notification
    )

    # 🚦 步骤3: 智能路由
    if content_type == 'image':
        logger.info(
            f"[Task {task_id}] Routing to IMAGE pipeline - "
            f"Platform: {platform}, URL: {clean_url}"
        )
        background_tasks.add_task(download_images_pipeline, task_id, clean_request)
        message = f"图片下载任务已创建 (平台: {platform})"

    else:  # video
        logger.info(
            f"[Task {task_id}] Routing to VIDEO pipeline - "
            f"Platform: {platform}, URL: {clean_url}"
        )
        background_tasks.add_task(process_video_pipeline, task_id, clean_request)
        message = f"视频处理任务已创建 (平台: {platform})"

    return ProcessMediaResponse(
        task_id=task_id,
        status="queued",
        message=message,
        title=title,
        platform=platform,
        content_type=content_type
    )


@app.get("/api/detect-type", response_model=DetectTypeResponse)
async def detect_type(url: str = Query(..., description="媒体链接或分享文本")):
    """
    仅检测链接的平台和类型，不进行实际处理

    用于前端或客户端预先判断内容类型

    Returns:
        平台、内容类型、原始类型代码、清理后的URL
    """
    content_info = await detect_content_info(url)

    return DetectTypeResponse(
        platform=content_info['platform'],
        content_type=content_info['content_type'],
        aweme_type=content_info['aweme_type'],
        clean_url=content_info['clean_url'],
        title=content_info['title']
    )

async def download_images_pipeline(task_id: str, request: ProcessMediaRequest):
    """图片下载处理管道"""
    r = await get_redis()

    try:
        # 步骤1: 下载图片
        await update_task_status(r, task_id, "downloading", "下载图片", 50)
        # request.url 已经是清理过的 URL，无需再次清理
        image_result = await download_video(request.url, task_id, request.with_watermark)

        if not image_result["success"]:
            raise Exception(f"图片下载失败: {image_result.get('message')}")

        # 检查是否为图片类型
        if image_result.get("data_type") != "image":
            raise Exception(f"URL不是图片类型，而是: {image_result.get('data_type')}")

        # 获取图片文件列表
        image_files = image_result["image_files"]

        # 更新任务标题为实际标题
        image_title = image_result.get("video_title", "")
        if image_title:
            updated_time = datetime.now().isoformat()
            await r.hset(f"task:{task_id}", mapping={
                "title": image_title,
                "updated_time": updated_time
            })

        # 完成
        result = {
            "data_type": "image",  # 标记为图片类型
            "image_files": image_files,  # 图片路径列表
            "image_count": image_result.get("image_count", 0),
            "platform": image_result.get("platform"),
            "video_id": image_result.get("video_id")
        }

        updated_time = datetime.now().isoformat()
        await r.hset(f"task:{task_id}", mapping={
            "status": "completed",
            "current_step": "finished",
            "progress": "100",
            "result": json.dumps(result),  # 使用JSON序列化而非str()
            "updated_time": updated_time
        })

        # 获取任务数据和通知配置
        task_data_full = await r.hgetall(f"task:{task_id}")
        notification_config = None
        if task_data_full and task_data_full.get(b"notification_config"):
            try:
                # import json removed - using global import
                notification_dict = json.loads(task_data_full[b"notification_config"].decode())
                notification_config = NotificationConfig(**notification_dict)
            except Exception as e:
                logger.error(f"Failed to parse notification config: {e}")

        if task_data_full:
            completion_data = {
                "task_id": task_id,
                "status": "completed",
                "current_step": "finished",
                "progress": 100,
                "updated_time": updated_time,
                "title": task_data_full.get(b"title", b"").decode(),
                "result": result,
                "url": task_data_full.get(b"url", b"").decode()
            }
            manager = get_notification_manager()
            await manager.notify_task_completed(task_id, completion_data, notification_config)

        logger.info(f"图片下载任务 {task_id} 处理完成")

    except Exception as e:
        logger.error(f"图片下载任务 {task_id} 处理失败: {str(e)}")
        updated_time = datetime.now().isoformat()
        await r.hset(f"task:{task_id}", mapping={
            "status": "failed",
            "current_step": "error",
            "error": str(e),
            "updated_time": updated_time
        })

        # 获取任务数据和通知配置
        task_data_full = await r.hgetall(f"task:{task_id}")
        notification_config = None
        if task_data_full and task_data_full.get(b"notification_config"):
            try:
                # import json removed - using global import
                notification_dict = json.loads(task_data_full[b"notification_config"].decode())
                notification_config = NotificationConfig(**notification_dict)
            except Exception as e:
                logger.error(f"Failed to parse notification config: {e}")

        if task_data_full:
            failure_data = {
                "task_id": task_id,
                "status": "failed",
                "current_step": "error",
                "progress": int(task_data_full.get(b"progress", b"0").decode()),
                "updated_time": updated_time,
                "title": task_data_full.get(b"title", b"").decode(),
                "error": str(e),
                "url": task_data_full.get(b"url", b"").decode()
            }
            manager = get_notification_manager()
            await manager.notify_task_failed(task_id, failure_data, notification_config)

async def process_video_pipeline(task_id: str, request: ProcessMediaRequest):
    """视频处理管道"""
    r = await get_redis()
    
    try:
        # 步骤1: 下载视频
        await update_task_status(r, task_id, "downloading", "下载视频", 20)
        video_result = await download_video(request.url, task_id, request.with_watermark)
        
        if not video_result["success"]:
            raise Exception(f"视频下载失败: {video_result.get('message')}")
        
        video_path = video_result["file_path"]
        
        # 更新任务标题为实际视频标题
        video_title = video_result.get("video_title", "")
        if video_title:
            updated_time = datetime.now().isoformat()
            await r.hset(f"task:{task_id}", mapping={
                "title": video_title,
                "updated_time": updated_time
            })
            
            # 获取通知配置
            task_data_full = await r.hgetall(f"task:{task_id}")
            notification_config = None
            if task_data_full.get(b"notification_config"):
                try:
                    notification_dict = json.loads(task_data_full[b"notification_config"].decode())
                    notification_config = NotificationConfig(**notification_dict)
                except Exception as e:
                    logger.error(f"Failed to parse notification config: {e}")
            
            # 通知标题已更新
            manager = get_notification_manager()
            await manager.send_notification("task_title_updated", task_id, {
                "task_id": task_id,
                "new_title": video_title,
                "updated_time": updated_time
            }, notification_config)
        
        # 步骤2: 转换音频 (本地FFmpeg)
        await update_task_status(r, task_id, "converting", "转换音频格式", 50)
        quality = getattr(request, 'quality', '4')
        audio_result = await convert_to_audio_local(video_path, task_id, quality)
        
        if not audio_result["success"]:
            raise Exception(f"音频转换失败: {audio_result.get('message')}")
        
        audio_path = audio_result["output_path"]
        
        # 步骤3: 语音识别
        await update_task_status(r, task_id, "transcribing", "语音识别", 80)
        asr_result = await transcribe_audio(audio_path, task_id)
        
        if not asr_result["success"]:
            raise Exception(f"语音识别失败: {asr_result.get('message')}")
        
        # 完成
        result = {
            "data_type": "video",  # 标记为视频类型
            "video_file": video_path,
            "audio_file": audio_path,
            "text_file": asr_result["output_path"],
            "text": asr_result["text"],
            "platform": video_result.get("platform"),
            "video_id": video_result.get("video_id")
        }

        updated_time = datetime.now().isoformat()
        await r.hset(f"task:{task_id}", mapping={
            "status": "completed",
            "current_step": "finished",
            "progress": "100",
            "result": json.dumps(result),  # 使用JSON序列化
            "updated_time": updated_time
        })
        
        # 获取任务数据和通知配置
        task_data_full = await r.hgetall(f"task:{task_id}")
        notification_config = None
        if task_data_full and task_data_full.get(b"notification_config"):
            try:
                # import json removed - using global import
                notification_dict = json.loads(task_data_full[b"notification_config"].decode())
                notification_config = NotificationConfig(**notification_dict)
            except Exception as e:
                logger.error(f"Failed to parse notification config: {e}")
        
        if task_data_full:
            completion_data = {
                "task_id": task_id,
                "status": "completed",
                "current_step": "finished",
                "progress": 100,
                "updated_time": updated_time,
                "title": task_data_full.get(b"title", b"").decode(),
                "result": result,
                "url": task_data_full.get(b"url", b"").decode()
            }
            manager = get_notification_manager()
            await manager.notify_task_completed(task_id, completion_data, notification_config)
        
        logger.info(f"任务 {task_id} 处理完成")
        
    except Exception as e:
        logger.error(f"任务 {task_id} 处理失败: {str(e)}")
        updated_time = datetime.now().isoformat()
        await r.hset(f"task:{task_id}", mapping={
            "status": "failed",
            "current_step": "error",
            "error": str(e),
            "updated_time": updated_time
        })
        
        # 获取任务数据和通知配置
        task_data_full = await r.hgetall(f"task:{task_id}")
        notification_config = None
        if task_data_full and task_data_full.get(b"notification_config"):
            try:
                # import json removed - using global import
                notification_dict = json.loads(task_data_full[b"notification_config"].decode())
                notification_config = NotificationConfig(**notification_dict)
            except Exception as e:
                logger.error(f"Failed to parse notification config: {e}")
        
        if task_data_full:
            failure_data = {
                "task_id": task_id,
                "status": "failed",
                "current_step": "error",
                "progress": int(task_data_full.get(b"progress", b"0").decode()),
                "updated_time": updated_time,
                "title": task_data_full.get(b"title", b"").decode(),
                "error": str(e),
                "url": task_data_full.get(b"url", b"").decode()
            }
            manager = get_notification_manager()
            await manager.notify_task_failed(task_id, failure_data, notification_config)

async def update_task_status(r, task_id: str, status: str, step: str, progress: int):
    """更新任务状态"""
    updated_time = datetime.now().isoformat()
    task_update = {
        "status": status,
        "current_step": step,
        "progress": str(progress),
        "updated_time": updated_time
    }
    
    await r.hset(f"task:{task_id}", mapping=task_update)
    
    # 获取任务数据和通知配置
    task_data_full = await r.hgetall(f"task:{task_id}")
    notification_config = None
    if task_data_full and task_data_full.get(b"notification_config"):
        try:
            notification_dict = json.loads(task_data_full[b"notification_config"].decode())
            notification_config = NotificationConfig(**notification_dict)
        except Exception as e:
            logger.error(f"Failed to parse notification config: {e}")
    
    if task_data_full:
        update_data = {
            "task_id": task_id,
            "status": status,
            "current_step": step,
            "progress": progress,
            "updated_time": updated_time,
            "title": task_data_full.get(b"title", b"").decode(),
            "url": task_data_full.get(b"url", b"").decode()
        }
        manager = get_notification_manager()
        await manager.notify_task_update(task_id, update_data, notification_config)

async def download_video(url: str, task_id: str, with_watermark: bool = False) -> Dict:
    """调用视频服务下载视频（使用共享存储，避免文件重复传输）"""
    # 增加超时时间以支持大文件下载
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
        params = {
            "url": url,
            "prefix": True,
            "with_watermark": with_watermark
        }

        # 使用普通的GET请求，但增加超时时间
        response = await client.get(f"{VIDEO_SERVICE_URL}/api/download_info", params=params)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"Video service response for {url}: success={result.get('success')}, data_type={result.get('data_type')}")

            if result.get("success"):
                # video-service 已经下载文件到共享存储
                # 我们只需要将文件路径转换为 orchestrator 的路径空间
                original_file_path = result.get("file_path")
                file_name = result.get("file_name")
                data_type = result.get("data_type", "video")
                logger.debug(f"Processing download: file_path={original_file_path}, file_name={file_name}, data_type={data_type}")

                # 将 video-service 的路径转换为 orchestrator 路径
                # 因为两者都挂载了同一个 volume (media-pipeline)
                # 处理相对路径和绝对路径两种情况
                if original_file_path and original_file_path.startswith('./downloads'):
                    # 相对路径：./downloads/... → /app/media/...
                    shared_file_path = original_file_path.replace('./downloads', '/app/media')
                elif original_file_path and original_file_path.startswith('/app/downloads'):
                    # 绝对路径：/app/downloads/... → /app/media/...
                    shared_file_path = original_file_path.replace('/app/downloads', '/app/media')
                elif original_file_path:
                    # 其他情况，尝试构造正确路径
                    shared_file_path = f"/app/media/{original_file_path.lstrip('./')}"
                else:
                    shared_file_path = None

                # 处理图片类型
                if data_type == "image":
                    # 处理图片文件列表
                    image_files = result.get("image_files", [])

                    # 路径转换（多个文件）
                    shared_image_paths = []
                    for img_file_path in image_files:
                        if not img_file_path:
                            logger.warning(f"Empty image file path in result")
                            continue

                        # 转换路径
                        if img_file_path.startswith('./downloads'):
                            shared_path = img_file_path.replace('./downloads', '/app/media')
                        elif img_file_path.startswith('/app/downloads'):
                            shared_path = img_file_path.replace('/app/downloads', '/app/media')
                        else:
                            shared_path = f"/app/media/{img_file_path.lstrip('./')}"

                        # 验证文件存在
                        if os.path.exists(shared_path):
                            shared_image_paths.append(shared_path)
                        else:
                            logger.warning(f"Image file not found: {shared_path}")

                    return {
                        "success": True,
                        "data_type": "image",
                        "image_files": shared_image_paths,  # 图片路径数组
                        "image_count": len(shared_image_paths),
                        "platform": result.get("platform"),
                        "video_id": result.get("video_id"),
                        "cached": result.get("cached", False),
                        "message": result.get("message", "图片下载成功"),
                        "video_title": result.get("video_title", ""),
                        "video_info": result.get("video_info", {})
                    }

                # 处理视频类型
                # 验证文件是否存在
                if os.path.exists(shared_file_path):
                    return {
                        "success": True,
                        "file_path": shared_file_path,
                        "file_name": file_name,
                        "platform": result.get("platform"),
                        "video_id": result.get("video_id"),
                        "data_type": data_type,
                        "cached": result.get("cached", False),
                        "message": result.get("message", "下载成功"),
                        "video_title": result.get("video_title", ""),  # 新增视频标题
                        "video_info": result.get("video_info", {})  # 新增视频详细信息
                    }
                else:
                    return {
                        "success": False,
                        "message": f"文件不存在于共享存储: {shared_file_path}"
                    }
            else:
                return {
                    "success": False,
                    "message": f"视频服务返回失败: {result}"
                }
        else:
            return {
                "success": False,
                "message": f"下载失败: {response.text}"
            }

async def convert_to_audio_local(video_path: str, task_id: str, quality: str = "4") -> Dict:
    """本地FFmpeg转换音频"""
    try:
        audio_filename = f"{task_id}.mp3"
        audio_path = os.path.join(MEDIA_PATH, "audio", audio_filename)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        
        # 构建FFmpeg命令
        cmd = [
            "ffmpeg", 
            "-i", video_path,
            "-vn",  # 无视频
            "-acodec", "libmp3lame",  # MP3编码器
            "-q:a", quality,  # 音质
            "-y",   # 覆盖输出文件
            audio_path
        ]
        
        logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")
        
        # 执行转换
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg错误: {result.stderr}")
            return {
                "success": False,
                "message": f"转换失败: {result.stderr}"
            }
        
        # 检查输出文件
        if not os.path.exists(audio_path):
            return {
                "success": False,
                "message": "转换完成但输出文件未生成"
            }
        
        # 获取文件大小
        file_size = os.path.getsize(audio_path)
        
        logger.info(f"转换成功: {video_path} -> {audio_path}")
        
        return {
            "success": True,
            "output_path": audio_path,
            "message": "转换成功",
            "file_size": file_size
        }
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg转换超时")
        return {
            "success": False,
            "message": "转换超时"
        }
    except Exception as e:
        logger.error(f"转换出错: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

async def transcribe_audio(audio_path: str, task_id: str) -> Dict:
    """调用ASR服务进行语音识别"""
    async with httpx.AsyncClient(timeout=600.0) as client:
        text_filename = f"{task_id}.txt"
        text_path = os.path.join(MEDIA_PATH, "text", text_filename)

        payload = {
            "audio_path": audio_path,
            "output_path": text_path
        }

        response = await client.post(f"{ASR_SERVICE_URL}/transcribe-path", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "success": False,
                "message": f"识别失败: {response.text}"
            }

@app.get("/api/tasks", response_model=TaskListResponse)
async def get_tasks(page: int = 1, page_size: int = 50):
    """Get paginated task list, sorted by creation time (newest first)"""
    r = await get_redis()
    
    try:
        # Get task IDs sorted by creation time (newest first)
        task_ids = await r.zrevrange("tasks:created", 0, -1)
        total = len(task_ids)
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_ids = task_ids[start_idx:end_idx]
        
        tasks = []
        for task_id in paginated_ids:
            # Convert bytes to string if needed
            task_id_str = task_id.decode() if isinstance(task_id, bytes) else task_id
            task_data = await r.hgetall(f"task:{task_id_str}")
            if task_data:
                try:
                    tasks.append(TaskListItem(
                        task_id=task_id_str,
                        title=task_data.get(b"title", b"Unknown Task").decode(),
                        status=TaskStatusEnum(task_data.get(b"status", b"queued").decode()),
                        created_time=datetime.fromisoformat(task_data.get(b"created_time", datetime.now().isoformat()).decode()),
                        progress=int(task_data.get(b"progress", b"0").decode())
                    ))
                except Exception as e:
                    logger.error(f"Error parsing task {task_id_str}: {e}")
                    continue
        
        return TaskListResponse(
            tasks=tasks,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tasks")

@app.get("/api/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(task_id: str):
    """Get detailed task information"""
    r = await get_redis()
    task_data = await r.hgetall(f"task:{task_id}")
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        result = None
        if task_data.get(b"result"):
            try:
                result_str = task_data.get(b"result").decode()
                result = eval(result_str) if result_str != "None" else None
            except:
                result = task_data.get(b"result").decode()
        
        return TaskDetailResponse(
            task_id=task_id,
            title=task_data.get(b"title", b"Unknown Task").decode(),
            status=TaskStatusEnum(task_data.get(b"status", b"queued").decode()),
            current_step=task_data.get(b"current_step", b"initialized").decode(),
            progress=int(task_data.get(b"progress", b"0").decode()),
            created_time=datetime.fromisoformat(task_data.get(b"created_time", datetime.now().isoformat()).decode()),
            updated_time=datetime.fromisoformat(task_data.get(b"updated_time", datetime.now().isoformat()).decode()),
            url=task_data.get(b"url", b"").decode(),
            result=result,
            error=task_data.get(b"error", b"").decode() if task_data.get(b"error") else None
        )
        
    except Exception as e:
        logger.error(f"Error parsing task detail {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse task data")

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a specific task"""
    r = await get_redis()
    
    # Check if task exists
    task_exists = await r.exists(f"task:{task_id}")
    if not task_exists:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete task data
    await r.delete(f"task:{task_id}")
    await r.zrem("tasks:created", task_id)
    
    # 通知任务删除
    manager = get_notification_manager()
    await manager.notify_task_deleted(task_id, {"task_id": task_id})
    
    return {"message": "Task deleted successfully"}

@app.delete("/api/tasks/completed")
async def clear_completed_tasks():
    """Delete all completed tasks"""
    r = await get_redis()
    
    # Get all task IDs
    task_ids = await r.zrange("tasks:created", 0, -1)
    deleted_count = 0
    
    for task_id in task_ids:
        task_data = await r.hgetall(f"task:{task_id}")
        if task_data and task_data.get(b"status", b"").decode() == "completed":
            await r.delete(f"task:{task_id}")
            await r.zrem("tasks:created", task_id)
            manager = get_notification_manager()
            await manager.notify_task_deleted(task_id, {"task_id": task_id})
            deleted_count += 1
    
    return {"message": f"Deleted {deleted_count} completed tasks"}

@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    r = await get_redis()
    task_data = await r.hgetall(f"task:{task_id}")
    
    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # Parse result safely
    result = None
    if task_data.get(b"result"):
        try:
            result_str = task_data.get(b"result").decode()
            result = eval(result_str) if result_str != "None" else None
        except:
            result = task_data.get(b"result").decode()
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task_data.get(b"status", b"").decode(),
        current_step=task_data.get(b"current_step", b"").decode(),
        progress=int(task_data.get(b"progress", b"0").decode()),
        result=result,
        error=task_data.get(b"error", b"").decode() if task_data.get(b"error") else None
    )

@app.get("/api/services/status")
async def get_services_status():
    """获取所有服务状态"""
    async with httpx.AsyncClient() as client:
        services = {
            "video-service": VIDEO_SERVICE_URL,
            "asr-service": ASR_SERVICE_URL
        }
        
        status = {}
        for name, base_url in services.items():
            try:
                response = await client.get(f"{base_url}/health", timeout=5.0)
                status[name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response": response.json() if response.status_code == 200 else None
                }
            except Exception as e:
                status[name] = {
                    "status": "unreachable",
                    "error": str(e)
                }
        
        return status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)