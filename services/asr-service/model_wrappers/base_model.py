"""
ASR 模型抽象基类

定义所有 ASR 模型的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any
from pathlib import Path


class BaseASRModel(ABC):
    """ASR 模型抽象基类"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        **kwargs
    ):
        """
        初始化 ASR 模型

        Args:
            model_path: 模型路径
            device: 设备 (cuda/cpu)
            **kwargs: 其他模型特定参数
        """
        self.model_path = model_path
        self.device = device
        self.model = None
        self._is_loaded = False

    @abstractmethod
    def load_model(self) -> None:
        """
        加载模型到内存

        Raises:
            RuntimeError: 模型加载失败
        """
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_path: Union[str, Path],
        language: str = "zh",
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
                "language": "zh",
                "segments": [
                    {"text": "第一句", "start": 0.0, "end": 2.5},
                    ...
                ]
            }

        Raises:
            FileNotFoundError: 音频文件不存在
            RuntimeError: 识别失败
        """
        pass

    @abstractmethod
    def transcribe_stream(
        self,
        audio_chunk: bytes,
        language: str = "zh",
        hotwords: Optional[List[str]] = None,
        is_final: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        流式转录音频块

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
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            {
                "name": "Fun-ASR-Nano-2512",
                "version": "2512",
                "languages": ["zh", "en", "ja", ...],
                "supports_streaming": True,
                "supports_hotwords": True,
                "vram_usage_mb": 4096
            }
        """
        pass

    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._is_loaded

    def unload_model(self) -> None:
        """卸载模型释放内存"""
        if self.model is not None:
            del self.model
            self.model = None
            self._is_loaded = False

            # 清理 GPU 缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    def validate_audio_file(self, audio_path: Union[str, Path]) -> None:
        """
        验证音频文件是否存在且可读

        Args:
            audio_path: 音频文件路径

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if not path.is_file():
            raise ValueError(f"路径不是文件: {audio_path}")

        # 检查文件扩展名
        supported_formats = {
            ".mp3", ".wav", ".m4a", ".flac", ".aac",
            ".ogg", ".wma", ".mp4", ".avi", ".mov"
        }
        if path.suffix.lower() not in supported_formats:
            raise ValueError(
                f"不支持的音频格式: {path.suffix}. "
                f"支持的格式: {', '.join(supported_formats)}"
            )

    def __enter__(self):
        """上下文管理器入口"""
        if not self.is_loaded():
            self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.unload_model()
        return False

    def __repr__(self) -> str:
        model_info = self.get_model_info() if self._is_loaded else {}
        return (
            f"{self.__class__.__name__}("
            f"model_path={self.model_path}, "
            f"device={self.device}, "
            f"loaded={self._is_loaded}, "
            f"info={model_info.get('name', 'Unknown')}"
            ")"
        )
