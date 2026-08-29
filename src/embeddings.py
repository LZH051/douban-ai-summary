"""Embedding 客户端。

两种实现：
- ApiEmbedder：OpenAI 兼容协议（AI_EMBEDDING_MODEL + AI_API_KEY/
  AI_BASE_URL），生产使用；
- HashingEmbedder：字符二元组哈希 + L2 归一化，零依赖零费用。
  没有语义能力（只有字面重合度），用于离线测试与未配置 key 时的
  本地演示——检索质量的差距本身就是"为什么需要真 embedding"的
  最好教材。

索引与查询必须使用同一种 embedder：build_index 会把 embedder
签名写进 collection 元数据，查询侧据此选择实现。
"""

import hashlib
import math
import os


class HashingEmbedder:
    """确定性的字符二元组哈希向量。无语义，仅字面匹配。"""

    signature = "hashing-bigram-v1"
    dimensions = 512

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            normalized = text.lower()
            for index in range(len(normalized) - 1):
                bigram = normalized[index:index + 2]
                digest = hashlib.md5(bigram.encode("utf-8")).digest()
                slot = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[slot] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class ApiEmbedder:
    """OpenAI 兼容 embedding 接口（如火山方舟 doubao-embedding）。"""

    def __init__(self):
        from ai_summary import get_ai_config

        api_key, base_url, _ = get_ai_config()
        self.model = os.getenv("AI_EMBEDDING_MODEL", "").strip()
        if not self.model:
            raise RuntimeError("AI 配置不完整：AI_EMBEDDING_MODEL")
        self.signature = f"api:{self.model}"
        from openai import OpenAI

        self.client = OpenAI(
            api_key=api_key, base_url=base_url,
            timeout=30.0, max_retries=0,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def api_embedder_configured() -> bool:
    return bool(
        os.getenv("AI_API_KEY", "").strip()
        and os.getenv("AI_BASE_URL", "").strip()
        and os.getenv("AI_EMBEDDING_MODEL", "").strip()
    )


def default_embedder():
    if api_embedder_configured():
        return ApiEmbedder()
    return HashingEmbedder()
