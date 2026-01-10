#!/usr/bin/env python3
"""
智能分句器测试脚本
"""

import sys
import logging
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sentence_segmenter import SentenceSegmenter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_segmentation():
    """测试 1: 基本分句功能"""
    print("\n" + "="*60)
    print("测试 1: 基本分句功能")
    print("="*60)

    segmenter = SentenceSegmenter()

    test_cases = [
        # 测试用例 1: 标准分句
        "今天天气很好。我去公园散步了。看到很多人在锻炼。",

        # 测试用例 2: 无标点的长句
        "我在使用GitHub进行版本控制然后使用Docker部署应用最后使用pytest进行测试",

        # 测试用例 3: 混合标点
        "这是第一句，包含逗号；这是第二句，用分号分隔！这是第三句？",

        # 测试用例 4: 技术术语
        "我们使用PyTorch训练模型，然后部署到Kubernetes集群，最后通过API提供服务。",
    ]

    for i, text in enumerate(test_cases, 1):
        print(f"\n用例 {i}:")
        print(f"输入: {text}")

        sentences = segmenter.segment(text)

        print(f"输出 ({len(sentences)} 句):")
        for j, sent in enumerate(sentences, 1):
            print(f"  {j}. {sent}")

    print("\n✓ 基本分句测试完成")


def test_long_sentence_splitting():
    """测试 2: 长句拆分"""
    print("\n" + "="*60)
    print("测试 2: 长句拆分")
    print("="*60)

    segmenter = SentenceSegmenter(
        max_sentence_length=50,
        split_long_sentences=True
    )

    # 超长句子（150+ 字符）
    long_text = (
        "在现代软件开发中我们使用各种工具和技术来提高开发效率"
        "比如使用Git进行版本控制使用Docker进行容器化部署"
        "使用Kubernetes进行容器编排使用Jenkins进行持续集成"
        "使用Prometheus进行监控使用ELK进行日志分析"
        "这些工具大大提高了我们的工作效率"
    )

    print(f"输入 ({len(long_text)} 字符):")
    print(f"{long_text}")

    sentences = segmenter.segment(long_text)

    print(f"\n输出 ({len(sentences)} 句):")
    for i, sent in enumerate(sentences, 1):
        print(f"  {i}. [{len(sent)}字] {sent}")

    # 统计信息
    stats = segmenter.get_stats(sentences)
    print(f"\n统计信息:")
    print(f"  总句数: {stats['total_sentences']}")
    print(f"  平均长度: {stats['avg_length']:.1f} 字符")
    print(f"  最短句: {stats['min_length']} 字符")
    print(f"  最长句: {stats['max_length']} 字符")

    print("\n✓ 长句拆分测试完成")


def test_short_sentence_merging():
    """测试 3: 短句合并"""
    print("\n" + "="*60)
    print("测试 3: 短句合并")
    print("="*60)

    segmenter = SentenceSegmenter(
        min_sentence_length=15,
        merge_short_sentences=True
    )

    # 多个短句
    short_text = "我很高兴。因为今天是周末。可以休息。不用上班。"

    print(f"输入:")
    print(f"{short_text}")

    sentences = segmenter.segment(short_text)

    print(f"\n输出 ({len(sentences)} 句):")
    for i, sent in enumerate(sentences, 1):
        print(f"  {i}. [{len(sent)}字] {sent}")

    print("\n✓ 短句合并测试完成")


def test_tech_terms_protection():
    """测试 4: 技术术语保护"""
    print("\n" + "="*60)
    print("测试 4: 技术术语保护")
    print("="*60)

    segmenter = SentenceSegmenter(
        protect_tech_terms=True
    )

    tech_text = (
        "我们使用GitHub进行版本控制。"
        "项目地址是https://github.com/user/repo。"
        "使用的版本是1.0.0。"
        "支持HTTP和HTTPS协议。"
        "使用PyTorch和TensorFlow训练模型。"
    )

    print(f"输入:")
    print(f"{tech_text}")

    sentences = segmenter.segment(tech_text)

    print(f"\n输出 ({len(sentences)} 句):")
    for i, sent in enumerate(sentences, 1):
        print(f"  {i}. {sent}")

    print("\n✓ 技术术语保护测试完成")


def test_conjunction_handling():
    """测试 5: 连接词处理"""
    print("\n" + "="*60)
    print("测试 5: 连接词处理")
    print("="*60)

    segmenter = SentenceSegmenter(
        merge_short_sentences=True
    )

    conjunction_text = "我想去公园。但是天气不好。所以我待在家里。"

    print(f"输入:")
    print(f"{conjunction_text}")

    sentences = segmenter.segment(conjunction_text)

    print(f"\n输出 ({len(sentences)} 句):")
    for i, sent in enumerate(sentences, 1):
        print(f"  {i}. {sent}")

    print("\n✓ 连接词处理测试完成")


def test_real_asr_output():
    """测试 6: 真实 ASR 输出"""
    print("\n" + "="*60)
    print("测试 6: 真实 ASR 输出模拟")
    print("="*60)

    segmenter = SentenceSegmenter()

    # 模拟 ASR 输出（可能没有标点，或标点不准确）
    asr_outputs = [
        "我在开发一个人工智能项目使用了PyTorch框架和Docker容器化部署并且使用了GitHub进行版本管理",
        "今天的会议讨论了三个议题首先是项目进度然后是预算问题最后是人员安排大家都很积极发言",
        "早上九点开始工作先检查邮件然后参加站会接着开始编码中午十二点吃饭下午继续工作五点下班",
    ]

    for i, text in enumerate(asr_outputs, 1):
        print(f"\nASR 输出 {i} ({len(text)} 字符):")
        print(f"原文: {text}")

        sentences = segmenter.segment(text)

        print(f"分句后 ({len(sentences)} 句):")
        for j, sent in enumerate(sentences, 1):
            print(f"  {j}. {sent}")

        stats = segmenter.get_stats(sentences)
        print(f"  平均句长: {stats['avg_length']:.1f} 字符")

    print("\n✓ 真实 ASR 输出测试完成")


def test_metadata():
    """测试 7: 元数据功能"""
    print("\n" + "="*60)
    print("测试 7: 元数据功能")
    print("="*60)

    segmenter = SentenceSegmenter()

    text = "这是第一句。这是第二句。这是第三句。"

    print(f"输入: {text}")

    segments = segmenter.segment_with_metadata(text)

    print(f"\n输出 ({len(segments)} 个片段):")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}. [{seg.start_pos}:{seg.end_pos}] {seg.text}")

    print("\n✓ 元数据功能测试完成")


def test_edge_cases():
    """测试 8: 边界情况"""
    print("\n" + "="*60)
    print("测试 8: 边界情况")
    print("="*60)

    segmenter = SentenceSegmenter()

    edge_cases = [
        ("", "空字符串"),
        ("   ", "仅空格"),
        ("你好", "极短文本"),
        ("。。。", "仅标点"),
        ("Hello World", "纯英文"),
        ("123456", "纯数字"),
        ("你好！！！", "多个相同标点"),
    ]

    for text, description in edge_cases:
        print(f"\n{description}: '{text}'")
        sentences = segmenter.segment(text)
        print(f"  结果: {sentences}")

    print("\n✓ 边界情况测试完成")


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 20)
    print("智能分句器测试")
    print("🚀 " * 20)

    # 运行所有测试
    test_basic_segmentation()
    test_long_sentence_splitting()
    test_short_sentence_merging()
    test_tech_terms_protection()
    test_conjunction_handling()
    test_real_asr_output()
    test_metadata()
    test_edge_cases()

    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
