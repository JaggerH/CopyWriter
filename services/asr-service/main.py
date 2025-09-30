from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from typing import Optional
import aiofiles

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ASR语音识别服务",
    description="提供中文语音识别功能",
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

# 全局模型变量
_model = None

def get_model():
    """延迟加载ASR模型"""
    global _model
    if _model is None:
        try:
            from funasr import AutoModel
            
            # 使用FunASR标准模型名称
            model_asr = 'damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch'
            model_vad = 'damo/speech_fsmn_vad_zh-cn-16k-common-pytorch'
            model_punc = 'damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch'
            
            # 检查GPU可用性
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"使用设备: {device}")
            if device == "cuda":
                logger.info(f"GPU信息: {torch.cuda.get_device_name(0)}")
                logger.info(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
            
            logger.info("正在加载ASR模型到GPU...")
            
            try:
                _model = AutoModel(
                    model=model_asr, 
                    model_revision="v2.0.4",
                    vad_model=model_vad,
                    vad_model_revision="v2.0.4",
                    punc_model=model_punc,
                    punc_model_revision="v2.0.4",
                    cache_dir="/app/models",
                    device=device  # 明确指定设备
                )
                logger.info(f"ASR模型加载成功 (设备: {device})")
            except Exception as e:
                logger.warning(f"标准模型加载失败，尝试简化配置: {e}")
                _model = AutoModel(
                    model="paraformer-zh", 
                    vad_model="fsmn-vad",
                    punc_model="ct-punc",
                    cache_dir="/app/models",
                    device=device
                )
                logger.info(f"ASR简化模型加载成功 (设备: {device})")
                
        except Exception as e:
            logger.error(f"ASR模型加载失败: {e}")
            raise Exception(f"模型加载失败: {e}")
    
    return _model

@app.get("/health")
async def health_check():
    """健康检查接口"""
    try:
        # 尝试加载模型（如果尚未加载）
        model = get_model()
        return {"status": "healthy", "service": "asr-service", "model_loaded": True}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "model_loaded": False}

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """
    语音识别接口
    - audio_path: 音频文件路径
    - output_path: 输出文本路径（可选）
    - language: 语言设置（暂时仅支持中文）
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
        
        # 获取模型
        logger.info(f"开始识别音频文件: {request.audio_path}")
        model = get_model()
        
        # 执行语音识别
        result = model.generate(input=request.audio_path)
        text = result[0]["text"]
        
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

@app.get("/models")
async def get_model_info():
    """获取模型信息"""
    try:
        model = get_model()
        return {
            "model_loaded": True,
            "supported_languages": ["zh-cn"],
            "model_type": "FunASR",
            "models": {
                "asr": "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                "vad": "damo/speech_fsmn_vad_zh-cn-16k-common-pytorch", 
                "punc": "damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
            }
        }
    except Exception as e:
        return {
            "model_loaded": False,
            "error": str(e)
        }

@app.post("/warm-up")
async def warm_up_model():
    """预热模型"""
    try:
        model = get_model()
        return {
            "success": True,
            "message": "模型预热完成"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型预热失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)