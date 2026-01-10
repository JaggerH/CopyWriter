from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
import os
import logging
from typing import Optional, List, Dict, Any
import aiofiles
import tempfile
import uuid
import json
from datetime import datetime
from pathlib import Path

# 导入场景热词系统
from scene_hotwords import (
    get_scene_hotwords,
    get_available_scenes,
    get_scene_description,
    get_scene_stats,
    check_duplicate,
    add_hotword as add_scene_hotword,
    remove_hotword as remove_scene_hotword,
    list_all_hotwords
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 热词文件路径
HOTWORDS_FILE = "/app/user_models/hotwords.json"

# 环境变量配置
ASR_MODEL = os.getenv("ASR_MODEL", "funasr-nano-2512")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
QDRANT_PATH = os.getenv("QDRANT_PATH", "/app/vector_db")
DEFAULT_SCENE = os.getenv("DEFAULT_SCENE", "tech")  # 新增：默认场景可配置
USER_SCENE_MERGE = os.getenv("USER_SCENE_MERGE", "")  # 新增：user场景要合并的预定义场景（逗号分隔）

app = FastAPI(
    title="ASR语音识别服务",
    description="提供中文语音识别功能 (Fun-ASR-Nano-2512 + RAG + 智能分句)",
    version="2.0.0"
)

class TranscribeRequest(BaseModel):
    audio_path: str
    output_path: Optional[str] = None
    language: Optional[str] = "zh-cn"
    scene: Optional[str] = DEFAULT_SCENE  # 场景类型（使用环境变量配置）

class TranscribeResponse(BaseModel):
    success: bool
    text: str
    output_path: str
    message: str
    confidence: Optional[float] = None
    sentences: Optional[List[str]] = None  # 智能分句结果
    language: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None  # 词级时间戳

class HotwordItem(BaseModel):
    """热词项（支持权重和分类）"""
    word: str
    weight: int = 10
    category: str = "general"
    context: Optional[str] = None

# 全局变量
_model = None
_rag_engine = None

def get_rag_engine():
    """延迟加载 RAG 引擎"""
    global _rag_engine
    if _rag_engine is None and RAG_ENABLED:
        try:
            from rag_engine import RAGHotwordEngine
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"初始化 RAG 引擎 (设备: {device})...")

            _rag_engine = RAGHotwordEngine(
                qdrant_path=QDRANT_PATH,
                device=device
            )

            # 从旧热词文件迁移数据到向量库
            if os.path.exists(HOTWORDS_FILE):
                try:
                    with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        words = data.get("words", [])
                        if words:
                            # 转换为新格式
                            hotwords = [
                                {"word": w, "weight": 10, "category": "general"}
                                for w in words
                            ]
                            count = _rag_engine.add_hotwords(hotwords)
                            logger.info(f"从旧格式迁移 {count} 个热词到 RAG 引擎")
                except Exception as e:
                    logger.warning(f"迁移旧热词失败: {e}")

            logger.info(f"✓ RAG 引擎初始化成功")
        except Exception as e:
            logger.error(f"RAG 引擎初始化失败: {e}")
            _rag_engine = None

    return _rag_engine

def get_model():
    """延迟加载 ASR 模型"""
    global _model
    if _model is None:
        try:
            import torch
            import sys

            # 检查 GPU 可用性
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"使用设备: {device}")
            if device == "cuda":
                logger.info(f"GPU 信息: {torch.cuda.get_device_name(0)}")
                logger.info(f"GPU 内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

            # 获取 RAG 引擎（如果启用）
            rag_engine = get_rag_engine() if RAG_ENABLED else None

            logger.info(f"正在加载 ASR 模型: {ASR_MODEL}...")

            # 加载 Fun-ASR-Nano-2512 模型
            sys.path.insert(0, str(Path(__file__).parent))
            from model_wrappers.funasr_nano_2512 import FunASRNano2512

            _model = FunASRNano2512(
                device=device,
                rag_engine=rag_engine,
                enable_rag=RAG_ENABLED,
                enable_smart_segmentation=True  # 默认启用智能分句
            )

            # 加载模型
            _model.load_model()

            # 获取模型信息
            info = _model.get_model_info()
            logger.info(f"✓ ASR 模型加载成功")
            logger.info(f"  名称: {info['name']}")
            logger.info(f"  提供商: {info['provider']}")
            logger.info(f"  GPU 显存: {info.get('vram_allocated_gb', 0):.2f} GB")
            logger.info(f"  RAG 热词: {'启用' if RAG_ENABLED else '禁用'}")
            logger.info(f"  智能分句: 启用")

        except Exception as e:
            logger.error(f"ASR 模型加载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f"模型加载失败: {e}")

    return _model

@app.get("/health")
async def health_check():
    """健康检查接口"""
    global _model
    # 检查模型是否已加载（不触发加载）
    model_loaded = _model is not None
    return {
        "status": "healthy",
        "service": "asr-service",
        "model_loaded": model_loaded
    }

@app.post("/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    scene: str = DEFAULT_SCENE  # 使用环境变量配置
):
    """
    语音识别接口 - 文件上传版本
    接受音频文件上传，返回识别文本（含智能分句）

    Args:
        file: 音频文件
        scene: 场景类型 (tech/medical/finance/education/ecommerce/general)
              - tech: 技术开发场景 (默认)
              - medical: 医疗健康场景
              - finance: 金融投资场景
              - education: 教育培训场景
              - ecommerce: 电商直播场景
              - general: 通用场景 (无热词)
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

        # 获取热词（支持 user 场景合并）
        if scene == "user":
            # user 场景：直接从 RAG 获取用户热词
            scene_hotwords = []

            # 1. 获取用户自定义热词
            rag_engine = get_rag_engine()
            if rag_engine:
                try:
                    user_hotwords_list = rag_engine.list_hotwords(limit=100)
                    user_hotwords = [h["word"] for h in user_hotwords_list]
                    scene_hotwords.extend(user_hotwords)
                    logger.info(f"从 RAG 获取 {len(user_hotwords)} 个用户热词")
                except Exception as e:
                    logger.warning(f"获取 RAG 用户热词失败: {e}")

            # 2. 合并预定义场景热词（如果配置了 USER_SCENE_MERGE）
            if USER_SCENE_MERGE:
                merge_scenes = [s.strip() for s in USER_SCENE_MERGE.split(",") if s.strip()]
                for merge_scene in merge_scenes:
                    merge_hotwords = get_scene_hotwords(merge_scene)
                    if merge_hotwords:
                        scene_hotwords.extend(merge_hotwords)
                        logger.info(f"合并 {merge_scene} 场景: {len(merge_hotwords)} 个热词")

            # 3. 去重
            scene_hotwords = list(set(scene_hotwords))

            scene_desc = f"用户自定义热词 (合并场景: {USER_SCENE_MERGE or '无'})"
            logger.info(f"场景: user ({scene_desc}), 总热词数（去重后）: {len(scene_hotwords)}")
        else:
            # 普通场景：使用预定义热词
            scene_hotwords = get_scene_hotwords(scene)
            scene_desc = get_scene_description(scene)
            logger.info(f"场景: {scene} ({scene_desc}), 热词数: {len(scene_hotwords)}")

        # 获取模型（自动包含 RAG 和智能分句）
        logger.info(f"开始识别音频...")
        model = get_model()

        # 执行语音识别（使用场景热词，不依赖 RAG 检索）
        result = model.transcribe(
            audio_path=temp_audio_path,
            language="auto",
            hotwords=scene_hotwords  # 直接传入场景热词
        )

        text = result["text"]
        logger.info(f"识别成功: {text[:50]}..." if len(text) > 50 else f"识别成功: {text}")

        # 返回增强结果
        return {
            "success": True,
            "text": text,
            "message": "识别成功",
            "confidence": result.get("confidence", 0.95),
            "sentences": result.get("sentences"),  # 智能分句结果
            "language": result.get("language"),
            "segments": result.get("segments"),  # 词级时间戳（如果有）
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
    - language: 语言设置
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

        # 获取热词（支持 user 场景合并）
        if request.scene == "user":
            # user 场景：直接从 RAG 获取用户热词
            scene_hotwords = []

            # 1. 获取用户自定义热词
            rag_engine = get_rag_engine()
            if rag_engine:
                try:
                    user_hotwords_list = rag_engine.list_hotwords(limit=100)
                    user_hotwords = [h["word"] for h in user_hotwords_list]
                    scene_hotwords.extend(user_hotwords)
                    logger.info(f"从 RAG 获取 {len(user_hotwords)} 个用户热词")
                except Exception as e:
                    logger.warning(f"获取 RAG 用户热词失败: {e}")

            # 2. 合并预定义场景热词（如果配置了 USER_SCENE_MERGE）
            if USER_SCENE_MERGE:
                merge_scenes = [s.strip() for s in USER_SCENE_MERGE.split(",") if s.strip()]
                for merge_scene in merge_scenes:
                    merge_hotwords = get_scene_hotwords(merge_scene)
                    if merge_hotwords:
                        scene_hotwords.extend(merge_hotwords)
                        logger.info(f"合并 {merge_scene} 场景: {len(merge_hotwords)} 个热词")

            # 3. 去重
            scene_hotwords = list(set(scene_hotwords))

            scene_desc = f"用户自定义热词 (合并场景: {USER_SCENE_MERGE or '无'})"
            logger.info(f"场景: user ({scene_desc}), 总热词数（去重后）: {len(scene_hotwords)}")
        else:
            # 普通场景：使用预定义热词
            scene_hotwords = get_scene_hotwords(request.scene)
            scene_desc = get_scene_description(request.scene)
            logger.info(f"场景: {request.scene} ({scene_desc}), 热词数: {len(scene_hotwords)}")

        # 获取模型（自动包含 RAG 和智能分句）
        logger.info(f"开始识别音频文件: {request.audio_path}")
        model = get_model()

        # 执行语音识别（使用场景热词，不依赖 RAG 检索）
        result = model.transcribe(
            audio_path=request.audio_path,
            language=request.language or "auto",
            hotwords=scene_hotwords  # 直接传入场景热词
        )

        text = result["text"]

        # 保存识别结果（如果启用了智能分句，保存分句后的文本）
        output_text = text
        if result.get("sentences"):
            # 使用分句后的文本，每句一行
            output_text = "\n".join(result["sentences"])

        async with aiofiles.open(request.output_path, "w", encoding="utf-8") as f:
            await f.write(output_text)

        logger.info(f"识别成功: {request.audio_path} -> {request.output_path}")

        return TranscribeResponse(
            success=True,
            text=text,
            output_path=request.output_path,
            message="识别成功",
            confidence=result.get("confidence", 0.95),
            sentences=result.get("sentences"),
            language=result.get("language"),
            segments=result.get("segments")
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
        info = model.get_model_info()

        return {
            "model_loaded": True,
            "model_type": "Fun-ASR-Nano-2512",
            "model_info": info,
            "features": {
                "rag_hotwords": RAG_ENABLED,
                "smart_segmentation": True,
                "streaming": False,  # Phase 3 skipped
            },
            "supported_languages": ["zh", "en", "auto"],
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
    try:
        # 优先从 RAG 引擎获取
        if RAG_ENABLED:
            rag_engine = get_rag_engine()
            if rag_engine:
                hotwords = rag_engine.list_hotwords(limit=1000)

                # 去重：保留每个词的最高权重记录
                word_map = {}
                for h in hotwords:
                    word = h["word"]
                    if word not in word_map or h.get("weight", 0) > word_map[word].get("weight", 0):
                        word_map[word] = h

                # 转换为列表，按权重排序
                unique_hotwords = sorted(word_map.values(), key=lambda x: -x.get("weight", 0))
                unique_words = [h["word"] for h in unique_hotwords]

                return {
                    "success": True,
                    "words": unique_words,  # 去重后的词列表
                    "hotwords": unique_hotwords,  # 完整信息（去重，包含权重、分类等）
                    "count": len(unique_words),
                    "source": "RAG"
                }

        # 降级：从文件读取（兼容旧版本）
        if os.path.exists(HOTWORDS_FILE):
            with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "success": True,
                    "words": data.get("words", []),
                    "count": len(data.get("words", [])),
                    "updated_at": data.get("updated_at", ""),
                    "source": "file"
                }

        return {"success": True, "words": [], "count": 0, "source": "empty"}

    except Exception as e:
        logger.error(f"获取热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取热词失败: {str(e)}")

@app.post("/hotwords")
async def update_hotwords(words: List[str]):
    """批量更新热词列表（兼容旧格式）"""
    try:
        # 优先使用 RAG 引擎
        if RAG_ENABLED:
            rag_engine = get_rag_engine()
            if rag_engine:
                # 转换为新格式
                hotwords = [
                    {"word": w, "weight": 10, "category": "general"}
                    for w in words
                ]

                # 清空旧热词，添加新热词
                # 注意：这里保持向后兼容，直接替换所有热词
                # TODO: 未来可以考虑更智能的合并策略
                count = rag_engine.add_hotwords(hotwords)

                logger.info(f"RAG 热词已更新: {count}个")
                return {
                    "success": True,
                    "count": count,
                    "message": f"成功更新 {count} 个热词到 RAG 引擎"
                }

        # 降级：保存到文件（兼容旧版本）
        os.makedirs(os.path.dirname(HOTWORDS_FILE), exist_ok=True)
        data = {
            "words": words,
            "updated_at": datetime.now().isoformat()
        }
        with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"热词已更新（文件）: {len(words)}个")
        return {
            "success": True,
            "count": len(words),
            "message": f"成功更新 {len(words)} 个热词"
        }

    except Exception as e:
        logger.error(f"更新热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新热词失败: {str(e)}")

@app.post("/hotwords/add")
async def add_hotword(word: str):
    """添加单个热词"""
    try:
        if not word or not word.strip():
            return {
                "success": False,
                "message": "热词为空"
            }

        word = word.strip()

        # 优先使用 RAG 引擎
        if RAG_ENABLED:
            rag_engine = get_rag_engine()
            if rag_engine:
                # 添加到 RAG 引擎
                count = rag_engine.add_hotwords([
                    {"word": word, "weight": 10, "category": "general"}
                ])

                # 获取总数
                stats = rag_engine.get_stats()
                total_count = stats.get("total_hotwords", count)

                logger.info(f"添加热词到 RAG: {word}")
                return {
                    "success": True,
                    "word": word,
                    "total_count": total_count,
                    "message": f"成功添加热词: {word}"
                }

        # 降级：使用文件
        data = {"words": []}
        if os.path.exists(HOTWORDS_FILE):
            with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        if word not in data["words"]:
            data["words"].append(word)
            data["updated_at"] = datetime.now().isoformat()

            os.makedirs(os.path.dirname(HOTWORDS_FILE), exist_ok=True)
            with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"添加热词到文件: {word}")
            return {
                "success": True,
                "word": word,
                "total_count": len(data["words"]),
                "message": f"成功添加热词: {word}"
            }
        else:
            return {
                "success": False,
                "message": "热词已存在"
            }

    except Exception as e:
        logger.error(f"添加热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加热词失败: {str(e)}")

@app.delete("/hotwords/{word}")
async def delete_hotword(word: str):
    """删除指定热词"""
    try:
        # 优先使用 RAG 引擎
        if RAG_ENABLED:
            rag_engine = get_rag_engine()
            if rag_engine:
                # 从 RAG 引擎删除
                success = rag_engine.delete_hotword(word)

                if success:
                    # 获取剩余数量
                    stats = rag_engine.get_stats()
                    remaining_count = stats.get("total_hotwords", 0)

                    logger.info(f"从 RAG 删除热词: {word}")
                    return {
                        "success": True,
                        "word": word,
                        "remaining_count": remaining_count,
                        "message": f"成功删除热词: {word}"
                    }
                else:
                    raise HTTPException(status_code=404, detail=f"热词不存在: {word}")

        # 降级：使用文件
        if not os.path.exists(HOTWORDS_FILE):
            raise HTTPException(status_code=404, detail="热词文件不存在")

        with open(HOTWORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if word in data["words"]:
            data["words"].remove(word)
            data["updated_at"] = datetime.now().isoformat()

            with open(HOTWORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"从文件删除热词: {word}")
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

# ==================== 新增 RAG 热词 API ====================

@app.post("/hotwords/add-enhanced")
async def add_enhanced_hotword(hotword: HotwordItem):
    """添加热词（支持权重和分类）"""
    try:
        if not RAG_ENABLED:
            raise HTTPException(
                status_code=501,
                detail="RAG 功能未启用，请使用 /hotwords/add"
            )

        rag_engine = get_rag_engine()
        if not rag_engine:
            raise HTTPException(
                status_code=500,
                detail="RAG 引擎初始化失败"
            )

        # 添加热词
        count = rag_engine.add_hotwords([hotword.dict()])

        # 获取总数
        stats = rag_engine.get_stats()
        total_count = stats.get("total_hotwords", count)

        logger.info(f"添加增强热词: {hotword.word} (权重: {hotword.weight}, 分类: {hotword.category})")
        return {
            "success": True,
            "word": hotword.word,
            "weight": hotword.weight,
            "category": hotword.category,
            "total_count": total_count,
            "message": f"成功添加热词: {hotword.word}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加增强热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加热词失败: {str(e)}")

@app.get("/hotwords/search")
async def search_hotwords(q: str, limit: int = 10):
    """搜索热词（基于语义相似度）"""
    try:
        if not RAG_ENABLED:
            raise HTTPException(
                status_code=501,
                detail="RAG 功能未启用"
            )

        rag_engine = get_rag_engine()
        if not rag_engine:
            raise HTTPException(
                status_code=500,
                detail="RAG 引擎初始化失败"
            )

        # 搜索热词
        results = rag_engine.search_hotwords(query=q, limit=limit)

        return {
            "success": True,
            "query": q,
            "results": results,
            "count": len(results)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@app.get("/hotwords/stats")
async def get_hotword_stats():
    """获取 RAG 热词统计信息"""
    try:
        if not RAG_ENABLED:
            raise HTTPException(
                status_code=501,
                detail="RAG 功能未启用"
            )

        rag_engine = get_rag_engine()
        if not rag_engine:
            raise HTTPException(
                status_code=500,
                detail="RAG 引擎初始化失败"
            )

        stats = rag_engine.get_stats()

        return {
            "success": True,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


# ==================== 场景热词管理接口 ====================
# 注意：具体路径必须在路径参数之前定义，否则会被路径参数匹配

@app.get("/scene-hotwords/list")
async def list_scene_hotwords():
    """获取所有场景的热词列表"""
    try:
        all_hotwords = list_all_hotwords()
        stats = get_scene_stats()

        return {
            "success": True,
            "scenes": {
                scene: {
                    "description": get_scene_description(scene),
                    "count": stats.get(scene, 0),
                    "hotwords": words
                }
                for scene, words in all_hotwords.items()
            },
            "total_scenes": len(all_hotwords)
        }

    except Exception as e:
        logger.error(f"获取场景热词列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取场景热词列表失败: {str(e)}")


@app.get("/scene-hotwords/scenes")
async def get_scenes():
    """获取所有可用场景"""
    try:
        scenes = get_available_scenes()
        stats = get_scene_stats()

        return {
            "success": True,
            "scenes": [
                {
                    "code": scene,
                    "description": get_scene_description(scene),
                    "count": stats.get(scene, 0)
                }
                for scene in scenes
            ],
            "total": len(scenes)
        }

    except Exception as e:
        logger.error(f"获取场景列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取场景列表失败: {str(e)}")


@app.get("/scene-hotwords/stats")
async def get_scene_stats_api():
    """获取场景热词统计信息"""
    try:
        stats = get_scene_stats()

        return {
            "success": True,
            "stats": stats,
            "total_hotwords": sum(stats.values()),
            "total_scenes": len(stats)
        }

    except Exception as e:
        logger.error(f"获取场景统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取场景统计失败: {str(e)}")


@app.get("/scene-hotwords/check-duplicate/{word}")
async def check_duplicate_api(word: str, scene: Optional[str] = None):
    """检查热词是否已存在"""
    try:
        duplicates = check_duplicate(word, scene)

        return {
            "success": True,
            "word": word,
            "exists": len(duplicates) > 0,
            "duplicates": duplicates
        }

    except Exception as e:
        logger.error(f"检查热词重复失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查热词重复失败: {str(e)}")


@app.get("/scene-hotwords/{scene}")
async def get_scene_hotwords_api(scene: str):
    """获取指定场景的热词列表"""
    try:
        hotwords = get_scene_hotwords(scene)
        description = get_scene_description(scene)

        return {
            "success": True,
            "scene": scene,
            "description": description,
            "hotwords": hotwords,
            "count": len(hotwords)
        }

    except Exception as e:
        logger.error(f"获取场景热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取场景热词失败: {str(e)}")


@app.post("/scene-hotwords/{scene}/add")
async def add_scene_hotword_api(scene: str, word: str, force: bool = False):
    """添加热词到指定场景（带防重检测）"""
    try:
        result = add_scene_hotword(word, scene, force)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加场景热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加场景热词失败: {str(e)}")


@app.delete("/scene-hotwords/{scene}/{word}")
async def remove_scene_hotword_api(scene: str, word: str):
    """从指定场景删除热词"""
    try:
        result = remove_scene_hotword(word, scene)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除场景热词失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除场景热词失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)