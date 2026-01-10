#!/usr/bin/env python3
"""
RAG 热词引擎

使用向量数据库 (Qdrant) 实现动态热词检索，提升 ASR 识别准确率
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import json
from dataclasses import dataclass, asdict

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class Hotword:
    """热词数据结构"""
    word: str
    weight: float = 10.0
    category: str = "general"
    context: str = ""
    usage_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hotword":
        """从字典创建"""
        return cls(**data)


class RAGHotwordEngine:
    """
    RAG 热词引擎

    使用 Qdrant 向量数据库和 SentenceTransformer 实现动态热词检索
    """

    COLLECTION_NAME = "hotwords"
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384维，快速
    VECTOR_SIZE = 384

    def __init__(
        self,
        qdrant_path: Union[str, Path] = "/app/vector_db",
        embedding_model: Optional[str] = None,
        device: str = "cuda",
    ):
        """
        初始化 RAG 热词引擎

        Args:
            qdrant_path: Qdrant 数据库路径（本地模式）
            embedding_model: 自定义 embedding 模型名称
            device: 设备 (cuda/cpu)
        """
        self.qdrant_path = Path(qdrant_path)
        self.qdrant_path.mkdir(parents=True, exist_ok=True)

        self.device = device
        self.embedding_model_name = embedding_model or self.EMBEDDING_MODEL

        logger.info(f"初始化 RAG 热词引擎: path={self.qdrant_path}, device={device}")

        # 初始化 Qdrant 客户端（本地模式）
        self.client = QdrantClient(path=str(self.qdrant_path))

        # 初始化 Embedding 模型
        logger.info(f"加载 Embedding 模型: {self.embedding_model_name}")
        self.embedder = SentenceTransformer(
            self.embedding_model_name,
            device=device
        )

        # 确保 collection 存在
        self._ensure_collection()

        logger.info("✓ RAG 热词引擎初始化成功")

    def _ensure_collection(self) -> None:
        """确保 Qdrant collection 存在"""
        try:
            # 检查 collection 是否存在
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.COLLECTION_NAME not in collection_names:
                logger.info(f"创建 Qdrant collection: {self.COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✓ Collection 创建成功")
            else:
                # 获取 collection 统计
                info = self.client.get_collection(self.COLLECTION_NAME)
                logger.info(f"Collection 已存在，包含 {info.points_count} 个热词")

        except Exception as e:
            logger.error(f"初始化 collection 失败: {e}", exc_info=True)
            raise

    def _embed_text(self, text: str) -> List[float]:
        """
        将文本转换为向量

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        try:
            # 使用 SentenceTransformer 生成 embedding
            embedding = self.embedder.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"向量化失败: {text}, 错误: {e}")
            raise

    def add_hotwords(
        self,
        hotwords: List[Union[str, Dict[str, Any], Hotword]],
        batch_size: int = 100
    ) -> int:
        """
        批量添加热词

        Args:
            hotwords: 热词列表，支持三种格式：
                      - str: 简单字符串，使用默认配置
                      - Dict: {"word": "GitHub", "weight": 10, "category": "tech"}
                      - Hotword: Hotword 对象
            batch_size: 批量处理大小

        Returns:
            成功添加的热词数量
        """
        try:
            logger.info(f"添加热词: {len(hotwords)} 个")

            # 标准化热词格式
            normalized_hotwords: List[Hotword] = []
            for hw in hotwords:
                if isinstance(hw, str):
                    normalized_hotwords.append(Hotword(word=hw))
                elif isinstance(hw, dict):
                    normalized_hotwords.append(Hotword.from_dict(hw))
                elif isinstance(hw, Hotword):
                    normalized_hotwords.append(hw)
                else:
                    logger.warning(f"不支持的热词格式: {type(hw)}, 跳过")
                    continue

            # 批量向量化和插入
            points = []
            for idx, hotword in enumerate(normalized_hotwords):
                # 生成向量（使用 word + context）
                text_to_embed = f"{hotword.word} {hotword.context}".strip()
                vector = self._embed_text(text_to_embed)

                # 创建 point
                point = PointStruct(
                    id=hash(hotword.word) & 0x7FFFFFFF,  # 使用 word 哈希作为 ID
                    vector=vector,
                    payload={
                        "word": hotword.word,
                        "weight": hotword.weight,
                        "category": hotword.category,
                        "context": hotword.context,
                        "usage_count": hotword.usage_count,
                    }
                )
                points.append(point)

                # 批量插入
                if len(points) >= batch_size:
                    self.client.upsert(
                        collection_name=self.COLLECTION_NAME,
                        points=points
                    )
                    logger.debug(f"已插入 {len(points)} 个热词")
                    points = []

            # 插入剩余的
            if points:
                self.client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=points
                )

            logger.info(f"✓ 成功添加 {len(normalized_hotwords)} 个热词")
            return len(normalized_hotwords)

        except Exception as e:
            logger.error(f"添加热词失败: {e}", exc_info=True)
            raise

    def remove_hotword(self, word: str) -> bool:
        """
        删除单个热词

        Args:
            word: 热词文本

        Returns:
            是否删除成功
        """
        try:
            point_id = hash(word) & 0x7FFFFFFF
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[point_id]
            )
            logger.info(f"✓ 已删除热词: {word}")
            return True
        except Exception as e:
            logger.error(f"删除热词失败: {word}, 错误: {e}")
            return False

    def delete_hotword(self, word: str) -> bool:
        """删除热词（remove_hotword 的别名）"""
        return self.remove_hotword(word)

    def search_hotwords(
        self,
        query: str,
        limit: int = 10,
        category: Optional[str] = None,
        min_weight: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索热词

        Args:
            query: 搜索查询
            limit: 返回结果数量
            category: 过滤分类
            min_weight: 最小权重过滤

        Returns:
            热词列表，按相似度排序
        """
        try:
            # 向量化查询
            query_vector = self._embed_text(query)

            # 构建过滤条件
            filter_conditions = []
            if category:
                filter_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category)
                    )
                )
            if min_weight is not None:
                from qdrant_client.models import Range
                filter_conditions.append(
                    FieldCondition(
                        key="weight",
                        range=Range(gte=min_weight)
                    )
                )

            query_filter = Filter(must=filter_conditions) if filter_conditions else None

            # 执行搜索（使用新版 Qdrant API）
            results = self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_vector,
                query_filter=query_filter,
                limit=limit
            )

            # 格式化结果
            hotwords = []
            for hit in results.points:
                hotwords.append({
                    "word": hit.payload["word"],
                    "weight": hit.payload["weight"],
                    "category": hit.payload["category"],
                    "context": hit.payload["context"],
                    "usage_count": hit.payload["usage_count"],
                    "similarity": hit.score,
                })

            logger.debug(f"搜索 '{query}': 找到 {len(hotwords)} 个热词")
            return hotwords

        except Exception as e:
            logger.error(f"搜索热词失败: {e}", exc_info=True)
            return []

    def retrieve_for_audio(
        self,
        ctc_text: str,
        top_k: int = 20,
        min_similarity: float = 0.3,
        boost_recent: bool = True
    ) -> List[str]:
        """
        为音频检索相关热词（核心方法）

        Args:
            ctc_text: CTC 解码的初步文本
            top_k: 返回 Top-K 个热词
            min_similarity: 最小相似度阈值
            boost_recent: 是否提升最近使用的热词权重

        Returns:
            热词列表（字符串格式，用于传递给 ASR 模型）
        """
        try:
            logger.debug(f"为音频检索热词: '{ctc_text[:50]}...'")

            # 搜索相关热词
            results = self.search_hotwords(
                query=ctc_text,
                limit=top_k * 2  # 多检索一些，后面筛选
            )

            # 过滤低相似度的
            filtered_results = [
                r for r in results
                if r["similarity"] >= min_similarity
            ]

            # 如果需要，提升高权重和高使用频率的热词
            if boost_recent:
                for r in filtered_results:
                    # 综合评分 = 相似度 * (1 + log(weight)) * (1 + log(usage_count + 1))
                    import math
                    boost = (1 + math.log(r["weight"])) * (1 + math.log(r["usage_count"] + 1))
                    r["final_score"] = r["similarity"] * boost

                # 按综合评分排序
                filtered_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
            else:
                # 按相似度排序
                filtered_results.sort(key=lambda x: x["similarity"], reverse=True)

            # 取 Top-K
            top_results = filtered_results[:top_k]

            # 提取热词文本
            hotword_list = [r["word"] for r in top_results]

            # 更新使用计数（异步更新，不影响性能）
            self._update_usage_counts([r["word"] for r in top_results])

            logger.info(f"✓ 检索到 {len(hotword_list)} 个相关热词")
            return hotword_list

        except Exception as e:
            logger.error(f"检索热词失败: {e}", exc_info=True)
            return []

    def _update_usage_counts(self, words: List[str]) -> None:
        """
        更新热词使用计数

        Args:
            words: 热词列表
        """
        try:
            for word in words:
                point_id = hash(word) & 0x7FFFFFFF
                # 读取当前 payload
                point = self.client.retrieve(
                    collection_name=self.COLLECTION_NAME,
                    ids=[point_id]
                )
                if point:
                    current_count = point[0].payload.get("usage_count", 0)
                    # 更新 payload
                    self.client.set_payload(
                        collection_name=self.COLLECTION_NAME,
                        payload={"usage_count": current_count + 1},
                        points=[point_id]
                    )
        except Exception as e:
            logger.warning(f"更新使用计数失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取引擎统计信息

        Returns:
            统计信息字典
        """
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "total_hotwords": info.points_count,
                "vector_size": self.VECTOR_SIZE,
                "embedding_model": self.embedding_model_name,
                "device": self.device,
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def list_hotwords(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        列出所有热词

        Args:
            limit: 最大返回数量

        Returns:
            热词列表（包含完整元数据）
        """
        try:
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=limit
            )

            hotwords = []
            for point in results[0]:
                hotwords.append({
                    "word": point.payload["word"],
                    "weight": point.payload["weight"],
                    "category": point.payload["category"],
                    "context": point.payload.get("context", ""),
                    "usage_count": point.payload.get("usage_count", 0),
                })

            logger.debug(f"列出 {len(hotwords)} 个热词")
            return hotwords

        except Exception as e:
            logger.error(f"列出热词失败: {e}")
            return []

    def export_hotwords(self, output_path: Union[str, Path]) -> int:
        """
        导出所有热词到 JSON 文件

        Args:
            output_path: 输出文件路径

        Returns:
            导出的热词数量
        """
        try:
            # 获取所有热词
            limit = 10000  # 假设最多 10k 个热词
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=limit
            )

            hotwords = []
            for point in results[0]:
                hotwords.append({
                    "word": point.payload["word"],
                    "weight": point.payload["weight"],
                    "category": point.payload["category"],
                    "context": point.payload["context"],
                    "usage_count": point.payload["usage_count"],
                })

            # 写入文件
            output_path = Path(output_path)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(hotwords, f, ensure_ascii=False, indent=2)

            logger.info(f"✓ 已导出 {len(hotwords)} 个热词到 {output_path}")
            return len(hotwords)

        except Exception as e:
            logger.error(f"导出热词失败: {e}", exc_info=True)
            return 0

    def import_hotwords(self, input_path: Union[str, Path]) -> int:
        """
        从 JSON 文件导入热词

        Args:
            input_path: 输入文件路径

        Returns:
            导入的热词数量
        """
        try:
            input_path = Path(input_path)
            with open(input_path, "r", encoding="utf-8") as f:
                hotwords = json.load(f)

            return self.add_hotwords(hotwords)

        except Exception as e:
            logger.error(f"导入热词失败: {e}", exc_info=True)
            return 0

    def clear_all(self) -> bool:
        """
        清空所有热词

        Returns:
            是否成功
        """
        try:
            # 删除并重新创建 collection
            self.client.delete_collection(collection_name=self.COLLECTION_NAME)
            self._ensure_collection()
            logger.info("✓ 已清空所有热词")
            return True
        except Exception as e:
            logger.error(f"清空热词失败: {e}")
            return False
