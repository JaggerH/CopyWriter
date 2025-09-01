from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import uuid
import os
import logging
import asyncio
import subprocess
from typing import Optional, Dict
import redis.asyncio as redis

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CopyWriter 任务编排服务",
    description="统一API网关，协调各微服务完成视频处理任务",
    version="1.0.0"
)

# 环境变量配置
VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://video-service:80")
ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL", "http://asr-service:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")

# Redis连接
redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

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

class TaskStatus(BaseModel):
    task_id: str
    status: str
    current_step: str
    progress: int
    result: Optional[Dict] = None
    error: Optional[str] = None

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
    await r.hset(f"task:{task_id}", mapping={
        "status": "queued",
        "current_step": "initialized",
        "progress": "0",
        "url": request.url,
        "chat_id": request.chat_id or ""
    })
    
    # 后台执行任务
    background_tasks.add_task(process_video_pipeline, task_id, request)
    
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
        
        # 步骤2: 转换音频 (本地FFmpeg)
        await update_task_status(r, task_id, "converting", "转换音频格式", 50)
        audio_result = await convert_to_audio_local(video_path, task_id, request.quality)
        
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
        
        await r.hset(f"task:{task_id}", mapping={
            "status": "completed",
            "current_step": "finished",
            "progress": "100",
            "result": str(result)
        })
        
        logger.info(f"任务 {task_id} 处理完成")
        
    except Exception as e:
        logger.error(f"任务 {task_id} 处理失败: {str(e)}")
        await r.hset(f"task:{task_id}", mapping={
            "status": "failed",
            "current_step": "error",
            "error": str(e)
        })

async def update_task_status(r, task_id: str, status: str, step: str, progress: int):
    """更新任务状态"""
    await r.hset(f"task:{task_id}", mapping={
        "status": status,
        "current_step": step,
        "progress": str(progress)
    })

async def download_video(url: str, task_id: str, with_watermark: bool = False) -> Dict:
    """调用视频服务下载视频"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        params = {
            "url": url,
            "prefix": True,
            "with_watermark": with_watermark
        }
        
        response = await client.get(f"{VIDEO_SERVICE_URL}/api/download", params=params)
        
        if response.status_code == 200:
            # 保存下载的视频文件到共享存储
            video_filename = f"{task_id}.mp4"
            video_path = os.path.join(MEDIA_PATH, "raw", video_filename)
            
            os.makedirs(os.path.dirname(video_path), exist_ok=True)
            
            with open(video_path, "wb") as f:
                f.write(response.content)
            
            return {
                "success": True,
                "file_path": video_path,
                "message": "下载成功"
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

@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    r = await get_redis()
    task_data = await r.hgetall(f"task:{task_id}")
    
    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskStatus(
        task_id=task_id,
        status=task_data.get(b"status", b"").decode(),
        current_step=task_data.get(b"current_step", b"").decode(),
        progress=int(task_data.get(b"progress", b"0").decode()),
        result=eval(task_data.get(b"result", b"None").decode()) if task_data.get(b"result") else None,
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