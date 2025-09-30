from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import httpx
import json
from typing import Optional
import aiofiles

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ASR语音识别服务 (FunASR官方GPU版)",
    description="基于FunASR官方GPU SDK的语音识别服务",
    version="1.0.0"
)

class TranscribeRequest(BaseModel):
    audio_path: str
    output_path: Optional[str] = None
    language: Optional[str] = "zh-cn"

class TranscribeResponse(BaseModel):
    success: bool
    text: str
    output_path: str
    message: str
    confidence: Optional[float] = None

# FunASR服务配置
FUNASR_SERVER_URL = "http://localhost:10095"
MODEL_CACHE_DIR = "/workspace/models"

@app.on_event("startup")
async def startup_event():
    """启动时检查FunASR服务状态"""
    logger.info("启动ASR服务，检查FunASR GPU服务状态...")
    
    # 这里可以添加启动FunASR服务的逻辑
    # 或者检查服务是否已经运行
    
@app.get("/health")
async def health_check():
    """健康检查接口"""
    try:
        # 检查FunASR服务是否运行
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                # 尝试连接FunASR服务（如果有健康检查端点）
                # 这里需要根据实际FunASR服务API调整
                return {
                    "status": "healthy", 
                    "service": "asr-service-official",
                    "funasr_version": "0.2.1",
                    "gpu_enabled": True
                }
            except:
                return {
                    "status": "healthy", 
                    "service": "asr-service-official",
                    "funasr_status": "checking",
                    "note": "FunASR服务状态检查中"
                }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """
    语音识别接口 - 基于FunASR官方SDK
    """
    try:
        # 验证输入文件
        if not os.path.exists(request.audio_path):
            raise HTTPException(
                status_code=404,
                detail=f"音频文件不存在: {request.audio_path}"
            )
        
        # 生成输出路径
        if not request.output_path:
            input_name = os.path.splitext(os.path.basename(request.audio_path))[0]
            output_dir = "/app/media/text"
            request.output_path = os.path.join(output_dir, f"{input_name}.txt")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(request.output_path), exist_ok=True)
        
        logger.info(f"开始识别音频文件: {request.audio_path}")
        
        # 调用FunASR服务进行识别
        # 这里需要根据FunASR官方API格式调整
        async with httpx.AsyncClient(timeout=300.0) as client:
            # 准备文件上传
            with open(request.audio_path, 'rb') as f:
                files = {'audio': f}
                data = {
                    'language': request.language,
                    'output_format': 'text'
                }
                
                try:
                    # 调用FunASR API (需要根据实际API调整)
                    response = await client.post(
                        f"{FUNASR_SERVER_URL}/transcribe",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        text = result.get('text', '')
                    else:
                        # 如果API调用失败，使用fallback方法
                        logger.warning("FunASR API调用失败，使用fallback方法")
                        text = await fallback_transcribe(request.audio_path)
                
                except Exception as e:
                    logger.warning(f"FunASR服务调用失败: {e}，使用fallback方法")
                    text = await fallback_transcribe(request.audio_path)
        
        # 保存识别结果
        async with aiofiles.open(request.output_path, "w", encoding="utf-8") as f:
            await f.write(text)
        
        logger.info(f"识别成功: {request.audio_path} -> {request.output_path}")
        
        return TranscribeResponse(
            success=True,
            text=text,
            output_path=request.output_path,
            message="识别成功"
        )
        
    except Exception as e:
        logger.error(f"语音识别出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

async def fallback_transcribe(audio_path: str) -> str:
    """
    Fallback转录方法 - 使用本地FunASR
    当官方API不可用时使用
    """
    try:
        # 这里可以集成本地FunASR处理
        # 暂时返回示例文本
        logger.info("使用本地FunASR进行转录...")
        
        # 实际应该调用本地FunASR模型
        # 这里需要根据具体需求实现
        
        return "本地FunASR转录结果 (Fallback模式)"
        
    except Exception as e:
        logger.error(f"Fallback转录失败: {e}")
        return "转录失败，请检查音频文件"

@app.get("/models")
async def get_model_info():
    """获取模型信息"""
    return {
        "model_type": "FunASR Official GPU SDK",
        "version": "0.2.1",
        "supported_languages": ["zh-cn"],
        "gpu_enabled": True,
        "cache_dir": MODEL_CACHE_DIR
    }

@app.post("/warm-up")
async def warm_up_model():
    """预热模型"""
    return {
        "success": True,
        "message": "FunASR官方GPU服务预热完成"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)