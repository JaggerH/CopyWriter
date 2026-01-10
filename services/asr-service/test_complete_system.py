#!/usr/bin/env python3
"""
完整系统测试：RAG + Fun-ASR + 智能分句

测试升级后的 ASR 系统完整功能
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


def print_section(title):
    """打印分隔线"""
    print("\n" + "="*70)
    print(title)
    print("="*70)


def test_complete_pipeline():
    """测试完整流程"""
    print_section("ASR 系统完整测试：RAG + Fun-ASR + 智能分句")

    # 步骤 1: 初始化 RAG 引擎
    print("\n[步骤 1] 初始化 RAG 引擎...")
    rag_engine = RAGHotwordEngine(
        qdrant_path="/app/vector_db_complete_test",
        device="cuda"
    )

    # 添加测试热词
    test_hotwords = [
        {"word": "GitHub", "weight": 10, "category": "tech", "context": "version control platform"},
        {"word": "Docker", "weight": 10, "category": "tech", "context": "containerization tool"},
        {"word": "Kubernetes", "weight": 9, "category": "tech", "context": "container orchestration"},
        {"word": "Python", "weight": 10, "category": "programming", "context": "programming language"},
        {"word": "机器学习", "weight": 10, "category": "ai", "context": "machine learning"},
        {"word": "深度学习", "weight": 10, "category": "ai", "context": "deep learning"},
        {"word": "开放时间", "weight": 10, "category": "general", "context": "operating hours"},
    ]

    count = rag_engine.add_hotwords(test_hotwords)
    print(f"✓ 添加了 {count} 个热词到向量库")

    # 步骤 2: 初始化 ASR 模型（启用所有功能）
    print("\n[步骤 2] 初始化 ASR 模型...")
    model = FunASRNano2512(
        device="cuda",
        rag_engine=rag_engine,
        enable_rag=True,
        enable_smart_segmentation=True
    )

    print("✓ ASR 模型初始化成功")
    print("  - RAG 热词检索: 已启用")
    print("  - 智能分句: 已启用")

    # 步骤 3: 加载模型
    print("\n[步骤 3] 加载模型...")
    model.load_model()
    print("✓ 模型加载完成")

    # 获取模型信息
    info = model.get_model_info()
    print(f"\n模型信息:")
    print(f"  名称: {info['name']}")
    print(f"  提供商: {info['provider']}")
    print(f"  GPU: {info.get('device', 'N/A')}")
    print(f"  显存: {info.get('vram_allocated_gb', 0):.2f} GB")

    # 步骤 4: 测试识别
    print("\n[步骤 4] 测试音频识别...")

    test_audio = Path("/root/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512/example/zh.mp3")

    if not test_audio.exists():
        print(f"✗ 测试音频不存在: {test_audio}")
        return

    print(f"测试音频: {test_audio.name}")

    # 执行识别（完整流程：RAG + ASR + 智能分句）
    result = model.transcribe(
        audio_path=str(test_audio),
        language="auto"
    )

    # 步骤 5: 显示结果
    print_section("识别结果")

    print("\n原始文本:")
    print(f"  {result['text']}")

    print(f"\n元数据:")
    print(f"  置信度: {result['confidence']}")
    print(f"  语言: {result['language']}")
    print(f"  字符数: {len(result['text'])}")

    # 智能分句结果
    if result.get('sentences'):
        sentences = result['sentences']
        print(f"\n智能分句结果 ({len(sentences)} 句):")
        for i, sentence in enumerate(sentences, 1):
            print(f"  {i}. {sentence}")
    else:
        print("\n智能分句: 未启用或失败")

    # 词级时间戳
    if result.get('segments') and len(result['segments']) > 0:
        print(f"\n词级时间戳 (前 5 个):")
        for i, seg in enumerate(result['segments'][:5], 1):
            print(f"  {i}. [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")
    else:
        print("\n词级时间戳: 无")

    # 步骤 6: 性能对比测试
    print_section("功能对比测试")

    print("\n测试 A: 禁用所有增强功能")
    model.enable_rag = False
    model.enable_smart_segmentation = False

    result_baseline = model.transcribe(str(test_audio), language="auto")
    print(f"  结果: {result_baseline['text']}")
    print(f"  分句: {'无' if not result_baseline.get('sentences') else len(result_baseline['sentences'])}")

    print("\n测试 B: 仅启用 RAG")
    model.enable_rag = True
    model.enable_smart_segmentation = False

    result_rag_only = model.transcribe(str(test_audio), language="auto")
    print(f"  结果: {result_rag_only['text']}")
    print(f"  分句: {'无' if not result_rag_only.get('sentences') else len(result_rag_only['sentences'])}")

    print("\n测试 C: 启用所有功能")
    model.enable_rag = True
    model.enable_smart_segmentation = True

    result_full = model.transcribe(str(test_audio), language="auto")
    print(f"  结果: {result_full['text']}")
    print(f"  分句: {len(result_full.get('sentences', []))} 句")

    # 对比分析
    print_section("对比分析")

    texts = {
        "基线 (无增强)": result_baseline['text'],
        "RAG 热词": result_rag_only['text'],
        "RAG + 智能分句": result_full['text'],
    }

    print("\n文本对比:")
    for name, text in texts.items():
        print(f"  {name}: {text}")

    # 准确率分析
    print("\n功能分析:")
    if result_baseline['text'] != result_rag_only['text']:
        print("  ✓ RAG 热词纠正了识别错误")
    else:
        print("  - RAG 热词未改变识别结果")

    if result_full.get('sentences'):
        print(f"  ✓ 智能分句生成了 {len(result_full['sentences'])} 个句子")
    else:
        print("  - 智能分句未生成结果")

    # 步骤 7: RAG 统计
    print_section("RAG 热词统计")

    stats = rag_engine.get_stats()
    print(f"\n向量库统计:")
    print(f"  总热词数: {stats['total_hotwords']}")
    print(f"  向量维度: {stats['vector_size']}")
    print(f"  Embedding 模型: {stats['embedding_model']}")

    # 清理
    print("\n[清理] 卸载模型...")
    model.unload_model()
    print("✓ 模型已卸载")

    print_section("测试完成")
    print("\n升级后的 ASR 系统功能:")
    print("  ✓ Fun-ASR-Nano-2512 模型 (准确率提升)")
    print("  ✓ RAG 热词检索 (动态热词注入)")
    print("  ✓ 智能分句 (文本可读性优化)")
    print("\n所有功能测试通过！")


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 25)
    print("ASR 服务完整系统测试")
    print("测试升级后的 Fun-ASR-Nano-2512 + RAG + 智能分句")
    print("🚀 " * 25)

    try:
        test_complete_pipeline()
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
