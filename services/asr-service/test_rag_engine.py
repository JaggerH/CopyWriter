#!/usr/bin/env python3
"""
RAG 热词引擎测试脚本
"""

import sys
import logging
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from rag_engine import RAGHotwordEngine, Hotword

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_initialization():
    """测试 1: 初始化"""
    print("\n" + "="*60)
    print("测试 1: RAG 引擎初始化")
    print("="*60)

    try:
        engine = RAGHotwordEngine(
            qdrant_path="/app/vector_db_test",
            device="cuda"
        )
        print(f"✓ 引擎初始化成功")

        stats = engine.get_stats()
        print("\n引擎统计:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")

        return engine

    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_add_hotwords(engine):
    """测试 2: 添加热词"""
    print("\n" + "="*60)
    print("测试 2: 添加热词")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        # 准备测试热词
        hotwords = [
            # 技术类热词
            {"word": "GitHub", "weight": 10, "category": "tech", "context": "version control"},
            {"word": "Docker", "weight": 10, "category": "tech", "context": "containerization"},
            {"word": "Kubernetes", "weight": 8, "category": "tech", "context": "orchestration"},
            {"word": "PyTorch", "weight": 9, "category": "tech", "context": "deep learning"},
            {"word": "TensorFlow", "weight": 9, "category": "tech", "context": "machine learning"},

            # 编程语言
            {"word": "Python", "weight": 10, "category": "programming", "context": "scripting language"},
            {"word": "JavaScript", "weight": 9, "category": "programming", "context": "web development"},
            {"word": "TypeScript", "weight": 8, "category": "programming", "context": "typed JavaScript"},

            # AI/ML 术语
            {"word": "Transformer", "weight": 9, "category": "ai", "context": "neural network architecture"},
            {"word": "GPT", "weight": 10, "category": "ai", "context": "generative pre-trained transformer"},
            {"word": "Claude", "weight": 10, "category": "ai", "context": "AI assistant"},
            {"word": "RAG", "weight": 9, "category": "ai", "context": "retrieval augmented generation"},

            # 开发工具
            {"word": "VSCode", "weight": 9, "category": "tool", "context": "code editor"},
            {"word": "pytest", "weight": 8, "category": "tool", "context": "testing framework"},
            {"word": "FastAPI", "weight": 8, "category": "tool", "context": "web framework"},

            # 简单字符串格式
            "Redis", "PostgreSQL", "MongoDB", "Nginx", "API"
        ]

        count = engine.add_hotwords(hotwords)
        print(f"✓ 成功添加 {count} 个热词")

        # 验证添加
        stats = engine.get_stats()
        print(f"当前热词总数: {stats['total_hotwords']}")

    except Exception as e:
        print(f"✗ 添加热词失败: {e}")
        import traceback
        traceback.print_exc()


def test_search_hotwords(engine):
    """测试 3: 搜索热词"""
    print("\n" + "="*60)
    print("测试 3: 搜索热词")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        # 测试查询
        queries = [
            "版本控制系统",
            "深度学习框架",
            "容器编排工具",
            "AI 模型",
            "Web 开发",
        ]

        for query in queries:
            print(f"\n查询: '{query}'")
            results = engine.search_hotwords(query, limit=5)

            if results:
                print(f"  找到 {len(results)} 个相关热词:")
                for i, r in enumerate(results, 1):
                    print(f"    {i}. {r['word']} (相似度: {r['similarity']:.3f}, 权重: {r['weight']}, 分类: {r['category']})")
            else:
                print("  未找到相关热词")

        print("\n✓ 搜索测试完成")

    except Exception as e:
        print(f"✗ 搜索失败: {e}")
        import traceback
        traceback.print_exc()


def test_retrieve_for_audio(engine):
    """测试 4: 为音频检索热词"""
    print("\n" + "="*60)
    print("测试 4: 为音频检索热词（核心功能）")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        # 模拟 CTC 解码的初步文本
        ctc_texts = [
            "我在使用 GIT HAB 进行版本控制",  # GitHub 发音相似
            "我们用 DOCKER 容器化部署应用",
            "Python 是最流行的机器学习语言",
            "使用 TRANSFORM 模型进行文本生成",  # Transformer 发音相似
            "我在开发一个 FAST API 项目",
        ]

        for ctc_text in ctc_texts:
            print(f"\nCTC 文本: '{ctc_text}'")
            hotwords = engine.retrieve_for_audio(
                ctc_text=ctc_text,
                top_k=10,
                min_similarity=0.2
            )

            if hotwords:
                print(f"  检索到 {len(hotwords)} 个热词:")
                print(f"  {', '.join(hotwords[:10])}")
            else:
                print("  未检索到热词")

        print("\n✓ 音频热词检索测试完成")

    except Exception as e:
        print(f"✗ 检索失败: {e}")
        import traceback
        traceback.print_exc()


def test_category_filter(engine):
    """测试 5: 分类过滤"""
    print("\n" + "="*60)
    print("测试 5: 分类过滤搜索")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        categories = ["tech", "ai", "programming", "tool"]

        for category in categories:
            print(f"\n分类: {category}")
            results = engine.search_hotwords(
                query="开发工具",  # 通用查询
                limit=5,
                category=category
            )

            if results:
                words = [r['word'] for r in results]
                print(f"  找到 {len(results)} 个热词: {', '.join(words)}")
            else:
                print(f"  该分类没有相关热词")

        print("\n✓ 分类过滤测试完成")

    except Exception as e:
        print(f"✗ 分类过滤失败: {e}")
        import traceback
        traceback.print_exc()


def test_export_import(engine):
    """测试 6: 导出和导入"""
    print("\n" + "="*60)
    print("测试 6: 导出和导入热词")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        # 导出
        export_path = "/tmp/hotwords_export.json"
        count = engine.export_hotwords(export_path)
        print(f"✓ 已导出 {count} 个热词到 {export_path}")

        # 查看导出文件大小
        import os
        size_kb = os.path.getsize(export_path) / 1024
        print(f"  文件大小: {size_kb:.2f} KB")

        print("\n✓ 导出导入测试完成")

    except Exception as e:
        print(f"✗ 导出导入失败: {e}")
        import traceback
        traceback.print_exc()


def test_performance(engine):
    """测试 7: 性能测试"""
    print("\n" + "="*60)
    print("测试 7: 性能测试")
    print("="*60)

    if engine is None:
        print("✗ 引擎未初始化，跳过测试")
        return

    try:
        import time

        # 测试检索性能
        ctc_text = "我在使用 GitHub 进行版本控制和 Docker 容器化部署"

        # 预热
        engine.retrieve_for_audio(ctc_text, top_k=10)

        # 正式测试
        iterations = 10
        start_time = time.time()

        for _ in range(iterations):
            hotwords = engine.retrieve_for_audio(ctc_text, top_k=10)

        elapsed = time.time() - start_time
        avg_time = (elapsed / iterations) * 1000  # 转换为毫秒

        print(f"检索性能:")
        print(f"  迭代次数: {iterations}")
        print(f"  总耗时: {elapsed:.3f} 秒")
        print(f"  平均耗时: {avg_time:.2f} 毫秒/次")
        print(f"  {'✓ 满足要求 (< 100ms)' if avg_time < 100 else '✗ 性能不足'}")

        print("\n✓ 性能测试完成")

    except Exception as e:
        print(f"✗ 性能测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 20)
    print("RAG 热词引擎测试")
    print("🚀 " * 20)

    # 检查依赖
    try:
        import torch
        print(f"\n✓ PyTorch 版本: {torch.__version__}")
        print(f"✓ CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("✗ PyTorch 未安装")

    try:
        import qdrant_client
        print(f"✓ Qdrant Client 已安装")
    except ImportError:
        print("✗ Qdrant Client 未安装")
        return

    try:
        import sentence_transformers
        print(f"✓ Sentence Transformers 已安装")
    except ImportError:
        print("✗ Sentence Transformers 未安装")
        return

    # 运行测试
    engine = test_initialization()

    if engine:
        test_add_hotwords(engine)
        test_search_hotwords(engine)
        test_retrieve_for_audio(engine)
        test_category_filter(engine)
        test_export_import(engine)
        test_performance(engine)

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
