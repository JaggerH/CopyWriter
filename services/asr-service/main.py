from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
import os
import logging
from typing import Optional, List
import aiofiles
import tempfile
import uuid
import json
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 热词文件路径
HOTWORDS_FILE = "/app/user_models/hotwords.json"

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

def load_hotwords():
    """
    动态加载热词列表
    每次识别时调用，读取最新的热词文件
    """
    if os.path.exists(HOTWORDS_FILE):
        try:
            with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                words = data.get("words", [])
                if words:
                    logger.info(f"加载热词: {len(words)}个 - {words[:5]}..." if len(words) > 5 else f"加载热词: {words}")
                    return " ".join(words)  # FunASR格式：空格分隔
        except Exception as e:
            logger.warning(f"加载热词失败: {e}")
    return ""  # 空字符串 = 不使用热词

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

@app.post("/transcribe")
async def transcribe_audio_file(file: UploadFile = File(...)):
    """
    语音识别接口 - 文件上传版本
    接受音频文件上传，返回识别文本
    """
    temp_audio_path = None
    try:
        # 创建临时文件保存上传的音频
        suffix = os.path.splitext(file.filename)[1] if file.filename else '.wav'
        temp_audio_path = f"/tmp/audio_{uuid.uuid4().hex}{suffix}"

        logger.info(f"接收上传文件: {file.filename}, 大小: {file.size if hasattr(file, 'size') else 'unknown'}")
        logger.info(f"保存到临时文件: {temp_audio_path}")

        # 保存上传的文件
        async with aiofiles.open(temp_audio_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        logger.info(f"文件已保存，大小: {len(content)} bytes")

        # 获取模型
        logger.info(f"开始识别音频...")
        model = get_model()

        # 加载热词
        hotwords = load_hotwords()

        # 执行语音识别（带热词）
        if hotwords:
            result = model.generate(input=temp_audio_path, hotword=hotwords)
        else:
            result = model.generate(input=temp_audio_path)
        text = result[0]["text"]

        logger.info(f"识别成功: {text[:50]}..." if len(text) > 50 else f"识别成功: {text}")

        return {
            "success": True,
            "text": text,
            "message": "识别成功"
        }

    except Exception as e:
        logger.error(f"语音识别出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 清理临时文件
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                logger.info(f"临时文件已删除: {temp_audio_path}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {e}")

@app.post("/transcribe-path", response_model=TranscribeResponse)
async def transcribe_audio_path(request: TranscribeRequest):
    """
    语音识别接口 - 文件路径版本（保留用于内部调用）
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

        # 加载热词
        hotwords = load_hotwords()

        # 执行语音识别（带热词）
        if hotwords:
            result = model.generate(input=request.audio_path, hotword=hotwords)
        else:
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

# ==================== 热词管理API ====================

@app.get("/hotwords")
async def get_hotwords():
    """获取当前热词列表"""
    if os.path.exists(HOTWORDS_FILE):
        try:
            with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "success": True,
                    "words": data.get("words", []),
                    "count": len(data.get("words", [])),
                    "updated_at": data.get("updated_at", "")
                }
        except Exception as e:
            logger.error(f"读取热词文件失败: {e}")
            raise HTTPException(status_code=500, detail=f"读取热词失败: {str(e)}")
    return {"success": True, "words": [], "count": 0}

@app.post("/hotwords")
async def update_hotwords(words: List[str]):
    """批量更新热词列表"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(HOTWORDS_FILE), exist_ok=True)

        # 保存热词
        data = {
            "words": words,
            "updated_at": datetime.now().isoformat()
        }
        with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"热词已更新: {len(words)}个")
        return {
            "success": True,
            "count": len(words),
            "message": f"成功更新{len(words)}个热词"
        }
    except Exception as e:
        logger.error(f"更新热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新热词失败: {str(e)}")

@app.post("/hotwords/add")
async def add_hotword(word: str):
    """添加单个热词"""
    try:
        # 读取现有热词
        data = {"words": []}
        if os.path.exists(HOTWORDS_FILE):
            with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        # 添加新热词（去重）
        if word and word not in data["words"]:
            data["words"].append(word)
            data["updated_at"] = datetime.now().isoformat()

            # 保存
            os.makedirs(os.path.dirname(HOTWORDS_FILE), exist_ok=True)
            with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"添加热词: {word}")
            return {
                "success": True,
                "word": word,
                "total_count": len(data["words"]),
                "message": f"成功添加热词: {word}"
            }
        else:
            return {
                "success": False,
                "message": "热词已存在或为空"
            }
    except Exception as e:
        logger.error(f"添加热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加热词失败: {str(e)}")

@app.delete("/hotwords/{word}")
async def delete_hotword(word: str):
    """删除指定热词"""
    try:
        if not os.path.exists(HOTWORDS_FILE):
            raise HTTPException(status_code=404, detail="热词文件不存在")

        # 读取现有热词
        with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 删除热词
        if word in data["words"]:
            data["words"].remove(word)
            data["updated_at"] = datetime.now().isoformat()

            # 保存
            with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"删除热词: {word}")
            return {
                "success": True,
                "word": word,
                "remaining_count": len(data["words"]),
                "message": f"成功删除热词: {word}"
            }
        else:
            raise HTTPException(status_code=404, detail=f"热词不存在: {word}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除热词失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)