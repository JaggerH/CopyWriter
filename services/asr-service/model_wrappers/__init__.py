"""
ASR 模型模块

支持多种 ASR 模型的统一接口
"""

from .base_model import BaseASRModel
from .funasr_nano_2512 import FunASRNano2512

__all__ = [
    "BaseASRModel",
    "FunASRNano2512",
]
