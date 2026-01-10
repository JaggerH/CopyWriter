#!/usr/bin/env python3
"""
RAG + Fun-ASR 集成测试

测试 RAG 热词检索与 ASR 识别的完整流程
"""

import sys
import logging
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from rag_engine import RAGHotwordEngine
from model_wrappers.funasr_nano_2512 import FunASRNano2512

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_initialization():
    """测试 1: 初始化 RAG 引擎和 ASR 模型"""
    print("\n" + "="*60)
    print("测试 1: 初始化 RAG 引擎和 ASR 模型")
    print("="*60)

    try:
        # 初始化 RAG 引擎
        rag_engine = RAGHotwordEngine(
            qdrant_path="/app/vector_db",
            device="cuda"
        )
        print("✓ RAG 引擎初始化成功")

        # 添加测试热词
        hotwords = [
            {"word": "GitHub", "weight": 10, "category": "tech", "context": "version control"},
            {"word": "Docker", "weight": 10, "category": "tech", "context": "containerization"},
            {"word": "Python", "weight": 10, "category": "programming", "context": "programming language"},
            {"word": "开放时间", "weight": 10, "category": "general", "context": "operating hours"},
            {"word": "测试", "weight": 10, "category": "general", "context": "testing"},
        ]
        count = rag_engine.add_hotwords(hotwords)
        print(f"✓ 添加了 {count} 个测试热词")

        # 初始化 ASR 模型（启用 RAG）
        model = FunASRNano2512(
            device="cuda",
            rag_engine=rag_engine,
            enable_rag=True
        )
        print("✓ ASR 模型初始化成功 (RAG enabled)")

        # 加载模型
        model.load_model()
        print("✓ 模型加载成功")

        return rag_engine, model

    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_rag_disabled(model):
    """测试 2: 禁用 RAG 的识别（基准）"""
    print("\n" + "="*60)
    print("测试 2: 禁用 RAG 的识别（基准）")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        # 临时禁用 RAG
        model.enable_rag = False

        # 使用模型自带的示例音频
        test_audio = Path("/root/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        print(f"测试音频: {test_audio}")
        print("模式: RAG 禁用")

        # 执行识别
        result = model.transcribe(
            audio_path=str(test_audio),
            language="auto"
        )

        print("\n识别结果 (不使用 RAG):")
        print(f"  文本: {result['text']}")
        print(f"  置信度: {result['confidence']}")

        # 恢复 RAG
        model.enable_rag = True

        print("\n✓ 基准测试完成")
        return result['text']

    except Exception as e:
        print(f"✗ 识别失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_rag_enabled(model):
    """测试 3: 启用 RAG 的识别"""
    print("\n" + "="*60)
    print("测试 3: 启用 RAG 的识别")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        # 确保 RAG 启用
        model.enable_rag = True

        # 使用模型自带的示例音频
        test_audio = Path("/root/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        print(f"测试音频: {test_audio}")
        print("模式: RAG 启用")

        # 执行识别（应该会自动检索热词）
        result = model.transcribe(
            audio_path=str(test_audio),
            language="auto"
        )

        print("\n识别结果 (使用 RAG):")
        print(f"  文本: {result['text']}")
        print(f"  置信度: {result['confidence']}")

        print("\n✓ RAG 识别测试完成")
        return result['text']

    except Exception as e:
        print(f"✗ 识别失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_with_manual_hotwords(model):
    """测试 4: 手动指定热词（跳过 RAG）"""
    print("\n" + "="*60)
    print("测试 4: 手动指定热词（跳过 RAG）")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        test_audio = Path("/root/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        # 手动指定热词（应该跳过 RAG 检索）
        manual_hotwords = ["开放时间", "营业时间", "工作时间"]
        print(f"手动热词: {manual_hotwords}")

        result = model.transcribe(
            audio_path=str(test_audio),
            language="auto",
            hotwords=manual_hotwords
        )

        print("\n识别结果 (手动热词):")
        print(f"  文本: {result['text']}")

        print("\n✓ 手动热词测试完成")

    except Exception as e:
        print(f"✗ 识别失败: {e}")
        import traceback
        traceback.print_exc()


def test_performance(model):
    """测试 5: 性能对比"""
    print("\n" + "="*60)
    print("测试 5: 性能对比 (RAG vs 非RAG)")
    print("="*60)

    if model is None:
        print("✗ 模型未加载，跳过测试")
        return

    try:
        import time

        test_audio = Path("/root/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512/example/zh.mp3")

        if not test_audio.exists():
            print(f"✗ 测试音频不存在: {test_audio}")
            return

        # 测试不使用 RAG
        model.enable_rag = False
        start = time.time()
        result_no_rag = model.transcribe(str(test_audio), language="auto")
        time_no_rag = time.time() - start

        # 测试使用 RAG
        model.enable_rag = True
        start = time.time()
        result_with_rag = model.transcribe(str(test_audio), language="auto")
        time_with_rag = time.time() - start

        print(f"\n性能对比:")
        print(f"  不使用 RAG: {time_no_rag:.3f} 秒")
        print(f"  使用 RAG:   {time_with_rag:.3f} 秒")
        print(f"  时间增加:   {time_with_rag - time_no_rag:.3f} 秒 ({(time_with_rag/time_no_rag - 1)*100:.1f}%)")

        print(f"\n结果对比:")
        print(f"  不使用 RAG: {result_no_rag['text']}")
        print(f"  使用 RAG:   {result_with_rag['text']}")

        print("\n✓ 性能测试完成")

    except Exception as e:
        print(f"✗ 性能测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 20)
    print("RAG + Fun-ASR 集成测试")
    print("🚀 " * 20)

    # 初始化
    rag_engine, model = test_initialization()

    if rag_engine and model:
        # 运行测试
        test_rag_disabled(model)
        test_rag_enabled(model)
        test_with_manual_hotwords(model)
        test_performance(model)

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
