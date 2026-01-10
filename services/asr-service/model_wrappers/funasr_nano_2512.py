"""
Fun-ASR-Nano-2512 模型实现

基于阿里通义实验室的 Fun-ASR-Nano-2512 模型
支持批量和流式语音识别，支持热词注入
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import torch

from .base_model import BaseASRModel

logger = logging.getLogger(__name__)


class FunASRNano2512(BaseASRModel):
    """
    Fun-ASR-Nano-2512 模型封装

    特性：
    - 端到端 LLM ASR 模型
    - 支持中英文无缝切换
    - 支持热词动态注入
    - 低延迟流式识别
    - 幻觉率降低 70%
    """

    DEFAULT_MODEL_PATH = "/app/models/funasr-nano-2512"

    # 支持的语言
    SUPPORTED_LANGUAGES = [
        "zh", "en", "ja", "ko", "yue",  # 中、英、日、韩、粤语
        "auto"  # 自动检测
    ]

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        use_itn: bool = True,
        use_punc: bool = True,
        batch_size: int = 1,
        rag_engine: Optional[Any] = None,
        enable_rag: bool = True,
        enable_smart_segmentation: bool = True,
        **kwargs
    ):
        """
        初始化 Fun-ASR-Nano-2512 模型

        Args:
            model_path: 模型路径（默认 ./models/funasr-nano-2512）
            device: 设备 (cuda/cpu)
            use_itn: 是否使用反文本正则化（数字转换等）
            use_punc: 是否使用标点预测
            batch_size: 批处理大小
            rag_engine: RAG 热词引擎实例（可选）
            enable_rag: 是否启用 RAG 热词检索
            enable_smart_segmentation: 是否启用智能分句
            **kwargs: 其他参数
        """
        model_path = model_path or self.DEFAULT_MODEL_PATH
        super().__init__(model_path=model_path, device=device, **kwargs)

        self.use_itn = use_itn
        self.use_punc = use_punc
        self.batch_size = batch_size

        # RAG 热词引擎
        self.rag_engine = rag_engine
        self.enable_rag = enable_rag and rag_engine is not None

        # 智能分句器
        self.enable_smart_segmentation = enable_smart_segmentation
        self.sentence_segmenter = None
        if enable_smart_segmentation:
            try:
                from sentence_segmenter import SentenceSegmenter
                self.sentence_segmenter = SentenceSegmenter(
                    min_sentence_length=10,
                    max_sentence_length=100,
                    target_sentence_length=40,
                )
                logger.info("✓ 智能分句器已启用")
            except ImportError as e:
                logger.warning(f"智能分句器加载失败: {e}")
                self.enable_smart_segmentation = False

        # 流式识别状态
        self._stream_cache = None

        logger.info(
            f"初始化 Fun-ASR-Nano-2512: path={model_path}, device={device}, "
            f"RAG={'enabled' if self.enable_rag else 'disabled'}, "
            f"SmartSeg={'enabled' if self.enable_smart_segmentation else 'disabled'}"
        )

    def load_model(self) -> None:
        """
        加载 Fun-ASR 模型到内存

        Raises:
            RuntimeError: 模型加载失败
        """
        if self._is_loaded:
            logger.info("模型已加载，跳过")
            return

        try:
            logger.info("开始加载 Fun-ASR-Nano-2512 模型...")

            # 检查模型路径
            model_path = Path(self.model_path)
            if not model_path.exists():
                raise FileNotFoundError(
                    f"模型路径不存在: {self.model_path}\n"
                    f"请确保已下载模型到该目录"
                )

            # 导入 FunASR
            try:
                from funasr import AutoModel
                import importlib.util
                import sys
            except ImportError as e:
                raise RuntimeError(
                    "FunASR 未安装。请运行: pip install funasr\n"
                    f"原始错误: {e}"
                )

            # 检查 CUDA 可用性
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA 不可用，自动切换到 CPU")
                self.device = "cpu"

            # 手动导入并注册 FunASRNano 模型类
            # 因为 FunASR 1.3.0 不包含此模型类，需要从下载的模型目录加载
            model_cache_dir = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "FunAudioLLM" / "Fun-ASR-Nano-2512"
            model_py_path = model_cache_dir / "model.py"
            ctc_py_path = model_cache_dir / "ctc.py"

            # 先加载 ctc.py（model.py 依赖它）
            if ctc_py_path.exists():
                logger.info(f"从 {ctc_py_path} 加载 CTC 模块...")
                spec = importlib.util.spec_from_file_location("ctc", ctc_py_path)
                if spec and spec.loader:
                    ctc_module = importlib.util.module_from_spec(spec)
                    sys.modules["ctc"] = ctc_module
                    spec.loader.exec_module(ctc_module)
                    logger.info("✓ CTC 模块加载成功")

            # 再加载 model.py
            if model_py_path.exists():
                logger.info(f"从 {model_py_path} 加载 FunASRNano 模型类...")
                # 动态加载 model.py 模块
                spec = importlib.util.spec_from_file_location("funasr_nano_model", model_py_path)
                if spec and spec.loader:
                    funasr_nano_module = importlib.util.module_from_spec(spec)
                    sys.modules["funasr_nano_model"] = funasr_nano_module
                    spec.loader.exec_module(funasr_nano_module)
                    logger.info("✓ FunASRNano 模型类注册成功")
            else:
                logger.warning(f"找不到 model.py 文件: {model_py_path}")
                logger.warning("尝试直接加载模型（可能失败）...")

            # 加载模型
            # Fun-ASR-Nano-2512 需要从 Hub 加载（会自动使用本地缓存）
            logger.info(f"加载 Fun-ASR-Nano-2512 模型...")
            model_name = "FunAudioLLM/Fun-ASR-Nano-2512"
            self.model = AutoModel(
                model=model_name,  # 使用 Hub 名称，funasr 会查找本地缓存
                trust_remote_code=True,  # Fun-ASR 需要信任远程代码
                hub="ms",  # 使用 ModelScope
                device=self.device,
                disable_update=True,  # 不自动更新模型
                disable_pbar=False,   # 显示进度条
            )

            self._is_loaded = True

            # 记录 GPU 使用情况
            if self.device == "cuda":
                vram_allocated = torch.cuda.memory_allocated() / 1024**3
                vram_reserved = torch.cuda.memory_reserved() / 1024**3
                logger.info(
                    f"✓ 模型加载成功！"
                    f"GPU 显存: 已分配 {vram_allocated:.2f} GB, "
                    f"已保留 {vram_reserved:.2f} GB"
                )
            else:
                logger.info("✓ 模型加载成功（CPU 模式）")

        except Exception as e:
            logger.error(f"模型加载失败: {e}", exc_info=True)
            raise RuntimeError(f"加载 Fun-ASR 模型失败: {e}")

    def transcribe(
        self,
        audio_path: Union[str, Path],
        language: str = "auto",
        hotwords: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (zh/en/auto)
            hotwords: 热词列表
            **kwargs: 其他参数

        Returns:
            {
                "text": "识别的文本",
                "confidence": 0.95,
                "language": "auto",
                "segments": [...]
            }

        Raises:
            FileNotFoundError: 音频文件不存在
            RuntimeError: 识别失败
        """
        # 确保模型已加载
        if not self._is_loaded:
            self.load_model()

        # 验证音频文件
        self.validate_audio_file(audio_path)

        # 验证语言
        if language not in self.SUPPORTED_LANGUAGES:
            logger.warning(
                f"不支持的语言: {language}, 使用 auto 代替。"
                f"支持的语言: {', '.join(self.SUPPORTED_LANGUAGES)}"
            )
            language = "auto"

        try:
            logger.info(f"开始识别: {audio_path}, 语言={language}")

            # 场景热词优先策略
            # 如果传入了热词（场景热词），直接使用，不进行 RAG 检索
            # RAG 检索逻辑已禁用，因为用文本语义匹配发音是错误的
            if hotwords and len(hotwords) > 0:
                logger.info(f"使用场景热词: {len(hotwords)} 个")
            elif self.enable_rag:
                # 降级：如果没有传入热词且启用了 RAG，从 RAG 获取所有用户热词（不做检索）
                logger.info("未指定场景热词，从 RAG 获取用户自定义热词")
                try:
                    # 直接获取所有用户热词，不做语义检索
                    all_user_hotwords = self.rag_engine.list_hotwords(limit=100)
                    if all_user_hotwords:
                        hotwords = [h["word"] for h in all_user_hotwords]
                        logger.info(f"从 RAG 获取 {len(hotwords)} 个用户热词")
                    else:
                        logger.info("RAG 中没有用户热词")
                except Exception as e:
                    logger.warning(f"从 RAG 获取热词失败: {e}")

            # 构建推理参数
            generate_kwargs = {
                "input": str(audio_path),
                "batch_size": self.batch_size,
            }

            # 添加热词（如果提供或从 RAG 检索到）
            if hotwords and len(hotwords) > 0:
                # Fun-ASR 热词格式：空格分隔的字符串
                hotword_str = " ".join(hotwords)
                generate_kwargs["hotword"] = hotword_str
                logger.info(f"使用热词 ({len(hotwords)} 个): {hotword_str[:100]}...")

            # 执行识别（第二遍，带热词）
            logger.debug(f"推理参数: {generate_kwargs}")
            result = self.model.generate(**generate_kwargs)

            # 解析结果
            if not result or len(result) == 0:
                raise RuntimeError("模型返回空结果")

            # Fun-ASR 返回格式: [{"text": "...", "timestamp": [...], ...}]
            first_result = result[0] if isinstance(result, list) else result

            text = first_result.get("text", "")
            timestamp = first_result.get("timestamp", [])

            # 构建分段信息（如果有时间戳）
            segments = []
            if timestamp and isinstance(timestamp, list):
                for ts in timestamp:
                    if isinstance(ts, (list, tuple)) and len(ts) >= 3:
                        # 格式: [start_ms, end_ms, word]
                        segments.append({
                            "text": ts[2] if len(ts) > 2 else "",
                            "start": ts[0] / 1000.0,  # 转换为秒
                            "end": ts[1] / 1000.0,
                        })

            # 智能分句处理（可选）
            sentences = None
            if self.enable_smart_segmentation and self.sentence_segmenter and text:
                try:
                    sentences = self.sentence_segmenter.segment(text)
                    logger.debug(f"智能分句: {len(text)} 字符 → {len(sentences)} 句")
                except Exception as e:
                    logger.warning(f"智能分句失败: {e}，使用原文")
                    sentences = None

            # 构建返回结果
            output = {
                "text": text,
                "confidence": 0.95,  # Fun-ASR 不提供置信度，使用默认值
                "language": language,
                "segments": segments,
                "sentences": sentences,  # 智能分句结果（如果启用）
                "raw_result": first_result,  # 保留原始结果
            }

            logger.info(
                f"✓ 识别完成: {len(text)} 字符, {len(segments)} 个片段"
                + (f", {len(sentences)} 句" if sentences else "")
            )
            return output

        except Exception as e:
            logger.error(f"识别失败: {e}", exc_info=True)
            raise RuntimeError(f"Fun-ASR 识别失败: {e}")

    def transcribe_stream(
        self,
        audio_chunk: bytes,
        language: str = "auto",
        hotwords: Optional[List[str]] = None,
        is_final: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        流式转录音频块

        注意：Fun-ASR-Nano-2512 的流式识别功能将在后续版本实现
        当前版本仅支持批量识别

        Args:
            audio_chunk: 音频数据块
            language: 语言代码
            hotwords: 热词列表
            is_final: 是否为最后一块
            **kwargs: 其他参数

        Returns:
            {
                "text": "部分识别文本",
                "is_final": False,
                "confidence": 0.85,
                "timestamp": 1.5
            }

        Raises:
            NotImplementedError: 流式识别尚未实现
        """
        # TODO: 实现流式识别
        # Fun-ASR 支持流式模式，需要使用不同的 API
        raise NotImplementedError(
            "流式识别功能将在 Phase 3 实现。"
            "当前版本请使用批量识别 transcribe() 方法"
        )

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型详细信息字典
        """
        info = {
            "name": "Fun-ASR-Nano-2512",
            "version": "2512",
            "provider": "Alibaba Tongyi Lab",
            "description": "端到端语音识别大模型，支持 RAG 热词检索",
            "languages": self.SUPPORTED_LANGUAGES,
            "supports_streaming": False,  # Phase 3 实现
            "supports_hotwords": True,
            "supports_rag": True,  # Phase 2 集成
            "model_size_gb": 1.88,
            "recommended_vram_gb": 4.0,
        }

        # 如果模型已加载，添加运行时信息
        if self._is_loaded and self.device == "cuda":
            try:
                vram_allocated = torch.cuda.memory_allocated() / 1024**3
                vram_reserved = torch.cuda.memory_reserved() / 1024**3
                info.update({
                    "vram_allocated_gb": round(vram_allocated, 2),
                    "vram_reserved_gb": round(vram_reserved, 2),
                    "device": torch.cuda.get_device_name(0),
                })
            except Exception as e:
                logger.warning(f"获取 GPU 信息失败: {e}")

        return info

    def warm_up(self, test_audio_path: Optional[str] = None) -> float:
        """
        预热模型（首次推理较慢）

        Args:
            test_audio_path: 测试音频路径（可选）

        Returns:
            预热耗时（秒）
        """
        if not self._is_loaded:
            self.load_model()

        logger.info("开始模型预热...")

        import time
        start_time = time.time()

        try:
            # 如果没有提供测试音频，使用模型自带的示例
            if test_audio_path is None:
                model_dir = Path(self.model_path)
                test_audio_path = model_dir / "zh.mp3"

                if not test_audio_path.exists():
                    logger.warning("未找到测试音频，跳过预热")
                    return 0.0

            # 执行一次推理
            result = self.transcribe(str(test_audio_path))

            elapsed = time.time() - start_time
            logger.info(f"✓ 模型预热完成，耗时 {elapsed:.2f} 秒")
            logger.debug(f"预热结果: {result.get('text', '')[:50]}...")

            return elapsed

        except Exception as e:
            logger.error(f"模型预热失败: {e}")
            return 0.0

    def set_hotwords(self, hotwords: List[str]) -> None:
        """
        设置热词列表（用于后续识别）

        Args:
            hotwords: 热词列表
        """
        if not isinstance(hotwords, list):
            raise ValueError("热词必须是列表类型")

        # 过滤空字符串
        hotwords = [w.strip() for w in hotwords if w and w.strip()]

        logger.info(f"设置热词: {len(hotwords)} 个")
        logger.debug(f"热词内容: {hotwords[:10]}...")  # 只显示前 10 个

        # Fun-ASR 热词在每次 transcribe 时传入
        # 这里只做验证和记录
        self._current_hotwords = hotwords

    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return [
            "mp3", "wav", "m4a", "flac", "aac",
            "ogg", "wma", "mp4", "avi", "mov"
        ]

    def __repr__(self) -> str:
        return (
            f"FunASRNano2512("
            f"device={self.device}, "
            f"loaded={self._is_loaded}, "
            f"model_path={self.model_path}"
            ")"
        )
