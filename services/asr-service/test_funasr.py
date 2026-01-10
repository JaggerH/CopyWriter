#!/usr/bin/env python3
"""
Fun-ASR-Nano-2512 模型测试脚本

测试模型加载、识别和热词功能
"""

import sys
import os
import logging
from pathlib import Path

# 添加 models 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from model_wrappers.funasr_nano_2512 import FunASRNano2512

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_model_loading():
    """测试 1: 模型加载"""
    print("\n" + "="*60)
    print("测试 1: 模型加载")
    print("="*60)

    try:
        # 创建模型实例
        model = FunASRNano2512(
            model_path="/app/models/funasr-nano-2512",
            device="cuda"  # 或 "cpu"
        )

        print(f"✓ 模型实例创建成功: {model}")

        # 加载模型
        model.load_model()
        print("✓ 模型加载成功")

        # 获取模型信息
        info = model.get_model_info()
        print("\n模型信息:")
        for key, value in info.items():
            print(f"  - {key}: {value}")

        return model

    except Exception as e:
        print(f"✗ 模型加载失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_transcription(model):
    """测试 2: 音频识别"""
    print("\n" + "="*60)
    print("测试 2: 音频识别（使用模型自带示例）")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        # 使用模型自带的中文示例音频
        test_audio = Path("/app/models/funasr-nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        print(f"测试音频: {test_audio}")

        # 执行识别
        result = model.transcribe(
            audio_path=str(test_audio),
            language="auto"
        )

        print("\n识别结果:")
        print(f"  文本: {result['text']}")
        print(f"  置信度: {result['confidence']}")
        print(f"  语言: {result['language']}")
        print(f"  片段数: {len(result['segments'])}")

        if result['segments']:
            print("\n前 3 个片段:")
            for i, seg in enumerate(result['segments'][:3]):
                print(f"    [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")

        print("\n✓ 音频识别测试通过")

    except Exception as e:
        print(f"✗ 音频识别失败: {e}")
        import traceback
        traceback.print_exc()


def test_hotwords(model):
    """测试 3: 热词功能"""
    print("\n" + "="*60)
    print("测试 3: 热词功能")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        test_audio = Path("/app/models/funasr-nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        # 定义热词
        hotwords = ["GitHub", "Docker", "Python", "测试", "识别"]
        print(f"使用热词: {hotwords}")

        # 带热词的识别
        result = model.transcribe(
            audio_path=str(test_audio),
            language="auto",
            hotwords=hotwords
        )

        print("\n识别结果（带热词）:")
        print(f"  文本: {result['text']}")

        print("\n✓ 热词功能测试通过")

    except Exception as e:
        print(f"✗ 热词测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_warm_up(model):
    """测试 4: 模型预热"""
    print("\n" + "="*60)
    print("测试 4: 模型预热")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        elapsed = model.warm_up()
        print(f"✓ 模型预热完成，耗时: {elapsed:.2f} 秒")

    except Exception as e:
        print(f"✗ 预热失败: {e}")


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 20)
    print("Fun-ASR-Nano-2512 模型测试")
    print("🚀 " * 20)

    # 检查依赖
    try:
        import torch
        print(f"\n✓ PyTorch 版本: {torch.__version__}")
        print(f"✓ CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✓ CUDA 版本: {torch.version.cuda}")
            print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("✗ PyTorch 未安装")
        return

    try:
        import funasr
        print(f"✓ FunASR 已安装")
    except ImportError:
        print("✗ FunASR 未安装，请运行: pip install funasr")
        return

    # 运行测试
    model = test_model_loading()

    if model:
        test_transcription(model)
        test_hotwords(model)
        test_warm_up(model)

        # 清理
        print("\n" + "="*60)
        print("清理资源")
        print("="*60)
        model.unload_model()
        print("✓ 模型已卸载")

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
