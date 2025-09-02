from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
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
    CreateTaskResponse, TaskListResponse, WebSocketMessage, TaskStatus as TaskStatusEnum
)
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

# 初始化URL解析器
url_parser = VideoURLParser()

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

async def notify_websocket_clients(message_type: str, task_id: str, data: dict):
    """Notify all WebSocket clients about task updates"""
    message = {
        "type": message_type,
        "task_id": task_id,
        "data": data
    }
    await manager.broadcast(message)

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
    
    # Notify WebSocket clients
    await notify_websocket_clients("task_created", task_id, {
        "task_id": task_id,
        "title": title,
        "status": "queued",
        "created_time": created_time,
        "progress": 0
    })
    
    return CreateTaskResponse(
        task_id=task_id,
        status="queued",
        message="任务已创建，开始处理",
        title=title
    )

@app.post("/api/process-video", response_model=ProcessVideoResponse)
async def process_video(request: ProcessVideoRequest, background_tasks: BackgroundTasks):
    """
    处理视频的主入口
    1. 下载视频
    2. 转换格式
    3. 语音识别
    4. 返回结果
    """
    task_id = str(uuid.uuid4())
    
    # 保存任务状态到Redis
    r = await get_redis()
    created_time = datetime.now().isoformat()
    
    # 使用新的URL解析逻辑
    clean_url = get_clean_video_url(request.url)
    title = extract_title_from_url_or_text(request.url)
    
    await r.hset(f"task:{task_id}", mapping={
        "status": "queued",
        "current_step": "initialized",
        "progress": "0",
        "url": clean_url,
        "chat_id": request.chat_id or "",
        "title": title,
        "created_time": created_time,
        "updated_time": created_time
    })
    
    # 创建一个使用清洁URL的ProcessVideoRequest对象传递给pipeline
    clean_request = ProcessVideoRequest(
        url=clean_url,
        quality=request.quality,
        with_watermark=request.with_watermark,
        chat_id=None  # 新任务API不使用chat_id
    )
    
    # 后台执行任务
    background_tasks.add_task(process_video_pipeline, task_id, clean_request)
    
    return ProcessVideoResponse(
        task_id=task_id,
        status="queued", 
        message="任务已加入队列，开始处理"
    )

async def process_video_pipeline(task_id: str, request: ProcessVideoRequest):
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
            
            # 通知WebSocket客户端标题已更新
            await notify_websocket_clients("task_title_updated", task_id, {
                "task_id": task_id,
                "new_title": video_title,
                "updated_time": updated_time
            })
        
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
            "video_path": video_path,
            "audio_path": audio_path,
            "text_path": asr_result["output_path"],
            "text": asr_result["text"]
        }
        
        updated_time = datetime.now().isoformat()
        await r.hset(f"task:{task_id}", mapping={
            "status": "completed",
            "current_step": "finished",
            "progress": "100",
            "result": str(result),
            "updated_time": updated_time
        })
        
        # Get task data for WebSocket notification
        task_data = await r.hgetall(f"task:{task_id}")
        if task_data:
            await notify_websocket_clients("task_update", task_id, {
                "task_id": task_id,
                "status": "completed",
                "current_step": "finished",
                "progress": 100,
                "updated_time": updated_time,
                "title": task_data.get(b"title", b"").decode(),
                "result": result
            })
        
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
        
        # Get task data for WebSocket notification
        task_data = await r.hgetall(f"task:{task_id}")
        if task_data:
            await notify_websocket_clients("task_update", task_id, {
                "task_id": task_id,
                "status": "failed",
                "current_step": "error",
                "progress": int(task_data.get(b"progress", b"0").decode()),
                "updated_time": updated_time,
                "title": task_data.get(b"title", b"").decode(),
                "error": str(e)
            })

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
    
    # Get task data for WebSocket notification
    task_data = await r.hgetall(f"task:{task_id}")
    if task_data:
        # Notify WebSocket clients
        await notify_websocket_clients("task_update", task_id, {
            "task_id": task_id,
            "status": status,
            "current_step": step,
            "progress": progress,
            "updated_time": updated_time,
            "title": task_data.get(b"title", b"").decode()
        })

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
            
            if result.get("success"):
                # video-service 已经下载文件到共享存储
                # 我们只需要将文件路径转换为 orchestrator 的路径空间
                original_file_path = result.get("file_path")
                file_name = result.get("file_name")
                
                # 将 video-service 的路径转换为 orchestrator 路径
                # 因为两者都挂载了同一个 volume (media-pipeline)
                # 处理相对路径和绝对路径两种情况
                if original_file_path.startswith('./downloads'):
                    # 相对路径：./downloads/... → /app/media/...
                    shared_file_path = original_file_path.replace('./downloads', '/app/media')
                elif original_file_path.startswith('/app/downloads'):
                    # 绝对路径：/app/downloads/... → /app/media/...
                    shared_file_path = original_file_path.replace('/app/downloads', '/app/media')
                else:
                    # 其他情况，尝试构造正确路径
                    shared_file_path = f"/app/media/{original_file_path.lstrip('./')}"
                
                # 验证文件是否存在
                if os.path.exists(shared_file_path):
                    return {
                        "success": True,
                        "file_path": shared_file_path,
                        "file_name": file_name,
                        "platform": result.get("platform"),
                        "video_id": result.get("video_id"),
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
        
        response = await client.post(f"{ASR_SERVICE_URL}/transcribe", json=payload)
        
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
    
    # Notify WebSocket clients
    await notify_websocket_clients("task_deleted", task_id, {"task_id": task_id})
    
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
            await notify_websocket_clients("task_deleted", task_id, {"task_id": task_id})
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