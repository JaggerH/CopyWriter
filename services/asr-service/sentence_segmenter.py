#!/usr/bin/env python3
"""
智能分句后处理器

对 ASR 识别结果进行智能分句，提升文本可读性
"""

import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SentenceSegment:
    """句子片段"""
    text: str
    start_pos: int
    end_pos: int
    is_complete: bool = True


class SentenceSegmenter:
    """
    智能分句器

    功能：
    1. 基于标点和语义的分句
    2. 长句拆分、短句合并
    3. 技术术语保护
    4. 规则引擎处理特殊情况
    """

    # 中文句子结束标点
    SENTENCE_END_MARKS = set(['。', '！', '？', '；', '…', '!', '?', ';'])

    # 句子内部标点（不应该分句）
    INTERNAL_MARKS = set(['，', '、', ',', '、'])

    # 连接词（可能需要合并句子）
    CONJUNCTIONS = {
        '但是', '然而', '而且', '并且', '因此', '所以', '因为', '由于',
        '虽然', '尽管', '不过', '可是', '于是', '接着', '然后', '接下来'
    }

    # 技术术语模式（不应该在其中分句）
    TECH_PATTERNS = [
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase: GitHub, PyTorch
        r'\b[A-Z]{2,}\b',  # 全大写缩写: API, HTTP, GPU
        r'\d+\.\d+\.\d+',  # 版本号: 1.0.0
        r'\w+://\S+',  # URL
    ]

    def __init__(
        self,
        min_sentence_length: int = 5,
        max_sentence_length: int = 150,
        target_sentence_length: int = 50,
        merge_short_sentences: bool = True,
        split_long_sentences: bool = True,
        protect_tech_terms: bool = True,
    ):
        """
        初始化分句器

        Args:
            min_sentence_length: 最小句子长度（字符）
            max_sentence_length: 最大句子长度（字符）
            target_sentence_length: 目标句子长度（字符）
            merge_short_sentences: 是否合并短句
            split_long_sentences: 是否拆分长句
            protect_tech_terms: 是否保护技术术语
        """
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length
        self.target_sentence_length = target_sentence_length
        self.merge_short_sentences = merge_short_sentences
        self.split_long_sentences = split_long_sentences
        self.protect_tech_terms = protect_tech_terms

        # 编译技术术语正则表达式
        self.tech_pattern = re.compile('|'.join(self.TECH_PATTERNS))

        # 尝试导入 jieba（中文分词）
        try:
            import jieba
            self.jieba = jieba
            self.has_jieba = True
            logger.info("✓ jieba 分词器已加载")
        except ImportError:
            self.jieba = None
            self.has_jieba = False
            logger.warning("jieba 未安装，将使用基础分句功能")

        logger.info(
            f"初始化智能分句器: min={min_sentence_length}, "
            f"max={max_sentence_length}, target={target_sentence_length}"
        )

    def segment(self, text: str) -> List[str]:
        """
        智能分句（主方法）

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        if not text or not text.strip():
            return []

        try:
            # 第一步：基于标点的初步分句
            initial_segments = self._split_by_punctuation(text)

            # 第二步：保护技术术语（标记不应该分句的位置）
            if self.protect_tech_terms:
                initial_segments = self._protect_tech_terms(initial_segments)

            # 第三步：合并过短的句子
            if self.merge_short_sentences:
                initial_segments = self._merge_short_sentences(initial_segments)

            # 第四步：拆分过长的句子
            if self.split_long_sentences:
                initial_segments = self._split_long_sentences(initial_segments)

            # 第五步：清理和后处理
            final_sentences = self._cleanup_sentences(initial_segments)

            logger.debug(f"分句完成: {len(text)} 字符 → {len(final_sentences)} 句")
            return final_sentences

        except Exception as e:
            logger.error(f"分句失败: {e}", exc_info=True)
            # 降级：返回原文本
            return [text.strip()]

    def _split_by_punctuation(self, text: str) -> List[str]:
        """
        基于标点符号的初步分句

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        sentences = []
        current_sentence = []

        for char in text:
            current_sentence.append(char)

            # 遇到句子结束标点
            if char in self.SENTENCE_END_MARKS:
                sentence = ''.join(current_sentence).strip()
                if sentence:
                    sentences.append(sentence)
                current_sentence = []

        # 添加最后一个句子（如果没有结束标点）
        if current_sentence:
            sentence = ''.join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)

        return sentences

    def _protect_tech_terms(self, sentences: List[str]) -> List[str]:
        """
        保护技术术语（避免在术语中间分句）

        Args:
            sentences: 句子列表

        Returns:
            处理后的句子列表
        """
        # 当前实现：技术术语保护在分句前已经通过标点判断完成
        # 这里可以进一步优化，例如检测跨句的技术术语并合并
        return sentences

    def _merge_short_sentences(self, sentences: List[str]) -> List[str]:
        """
        合并过短的句子

        Args:
            sentences: 句子列表

        Returns:
            合并后的句子列表
        """
        if not sentences:
            return []

        merged = []
        buffer = []

        for sentence in sentences:
            buffer.append(sentence)
            buffer_text = ''.join(buffer)

            # 如果缓冲区长度达到最小要求，或者是最后一句
            if len(buffer_text) >= self.min_sentence_length or sentence == sentences[-1]:
                # 检查下一句是否以连接词开头（如果是，继续合并）
                if sentence != sentences[-1]:
                    next_idx = sentences.index(sentence) + 1
                    if next_idx < len(sentences):
                        next_sentence = sentences[next_idx]
                        # 检查是否以连接词开头
                        starts_with_conjunction = any(
                            next_sentence.startswith(conj)
                            for conj in self.CONJUNCTIONS
                        )
                        if starts_with_conjunction and len(buffer_text) < self.target_sentence_length:
                            continue  # 继续累积

                # 输出合并后的句子
                merged_text = ''.join(buffer).strip()
                if merged_text:
                    merged.append(merged_text)
                buffer = []

        return merged

    def _split_long_sentences(self, sentences: List[str]) -> List[str]:
        """
        拆分过长的句子

        Args:
            sentences: 句子列表

        Returns:
            拆分后的句子列表
        """
        result = []

        for sentence in sentences:
            if len(sentence) <= self.max_sentence_length:
                result.append(sentence)
                continue

            # 句子过长，需要拆分
            logger.debug(f"拆分长句: {len(sentence)} 字符")

            # 尝试在逗号处拆分
            subsegments = self._split_at_commas(sentence)

            # 如果拆分后仍然过长，强制按长度拆分
            for seg in subsegments:
                if len(seg) <= self.max_sentence_length:
                    result.append(seg)
                else:
                    # 强制拆分
                    result.extend(self._force_split(seg, self.max_sentence_length))

        return result

    def _split_at_commas(self, sentence: str) -> List[str]:
        """
        在逗号处拆分句子

        Args:
            sentence: 输入句子

        Returns:
            拆分后的子句列表
        """
        # 按逗号拆分
        parts = re.split(r'([，,])', sentence)

        # 重新组合（保留逗号）
        segments = []
        current = []

        for i, part in enumerate(parts):
            current.append(part)

            # 如果是逗号，且累积长度达到目标
            if part in ['，', ','] and len(''.join(current)) >= self.target_sentence_length // 2:
                seg = ''.join(current).strip()
                if seg:
                    segments.append(seg)
                current = []

        # 添加剩余部分
        if current:
            seg = ''.join(current).strip()
            if seg:
                segments.append(seg)

        return segments if segments else [sentence]

    def _force_split(self, sentence: str, max_len: int) -> List[str]:
        """
        强制按长度拆分句子（最后手段）

        Args:
            sentence: 输入句子
            max_len: 最大长度

        Returns:
            拆分后的片段
        """
        segments = []
        start = 0

        while start < len(sentence):
            end = min(start + max_len, len(sentence))
            segment = sentence[start:end].strip()
            if segment:
                segments.append(segment)
            start = end

        return segments

    def _cleanup_sentences(self, sentences: List[str]) -> List[str]:
        """
        清理和后处理句子

        Args:
            sentences: 句子列表

        Returns:
            清理后的句子列表
        """
        cleaned = []

        for sentence in sentences:
            # 去除首尾空格
            sentence = sentence.strip()

            # 过滤空句子
            if not sentence:
                continue

            # 确保句子以适当的标点结束
            if sentence and sentence[-1] not in self.SENTENCE_END_MARKS:
                # 如果没有结束标点，添加句号
                if any(c.isalnum() or c in '，、,、' for c in sentence):
                    sentence += '。'

            cleaned.append(sentence)

        return cleaned

    def segment_with_metadata(self, text: str) -> List[SentenceSegment]:
        """
        分句并返回元数据（位置信息）

        Args:
            text: 输入文本

        Returns:
            包含元数据的句子片段列表
        """
        sentences = self.segment(text)
        segments = []

        current_pos = 0
        for sentence in sentences:
            # 在原文中查找句子位置
            start = text.find(sentence, current_pos)
            if start == -1:
                start = current_pos

            end = start + len(sentence)

            segments.append(SentenceSegment(
                text=sentence,
                start_pos=start,
                end_pos=end,
                is_complete=True
            ))

            current_pos = end

        return segments

    def get_stats(self, sentences: List[str]) -> dict:
        """
        获取分句统计信息

        Args:
            sentences: 句子列表

        Returns:
            统计信息字典
        """
        if not sentences:
            return {
                "total_sentences": 0,
                "total_chars": 0,
                "avg_length": 0,
                "min_length": 0,
                "max_length": 0,
            }

        lengths = [len(s) for s in sentences]

        return {
            "total_sentences": len(sentences),
            "total_chars": sum(lengths),
            "avg_length": sum(lengths) / len(lengths),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "length_distribution": {
                "short (<20 chars)": sum(1 for l in lengths if l < 20),
                "medium (20-50 chars)": sum(1 for l in lengths if 20 <= l <= 50),
                "long (>50 chars)": sum(1 for l in lengths if l > 50),
            }
        }
