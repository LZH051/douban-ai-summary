"""语义索引：Chroma 本地持久化向量库。

- 文档 = 片名 + 短评/简介 +（如有）AI 摘要，按 douban_id upsert，
  重跑幂等且 embedding 只算一次（成本控制：内容没变就跳过）；
- embedder 签名记录在索引目录的 embedder.json，查询侧用同一种实现；
- 路径默认 database/chroma/，可用 CHROMA_PATH 覆盖（测试用）。
"""

import hashlib
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from web_database import PROJECT_ROOT, SessionLocal
from web_models import Movie

logger = logging.getLogger(__name__)

COLLECTION_NAME = "movies"
BATCH_SIZE = 32


def chroma_path() -> Path:
    configured = os.getenv("CHROMA_PATH", "").strip()
    return Path(configured) if configured else PROJECT_ROOT / "database" / "chroma"


def get_collection(create: bool = True):
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_path()))
    if create:
        return client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(COLLECTION_NAME)


def build_document(movie: Movie) -> str:
    parts = [movie.title, movie.introduction]
    if movie.ai_summary:
        parts.append(movie.ai_summary.summary)
    return "。".join(part.strip() for part in parts if part and part.strip())


def content_hash(text: str, signature: str) -> str:
    return hashlib.md5(f"{signature}|{text}".encode("utf-8")).hexdigest()


SIGNATURE_FILE_NAME = "embedder.json"


def write_embedder_signature(signature: str) -> None:
    import json

    path = chroma_path() / SIGNATURE_FILE_NAME
    path.write_text(json.dumps({"embedder": signature}), encoding="utf-8")


def build_index(embedder) -> dict:
    collection = get_collection()
    write_embedder_signature(embedder.signature)

    with SessionLocal() as database:
        movies = database.scalars(
            select(Movie).options(selectinload(Movie.ai_summary))
        ).all()

    existing = collection.get(include=["metadatas"])
    existing_hashes = {
        item_id: (metadata or {}).get("content_hash")
        for item_id, metadata in zip(existing["ids"], existing["metadatas"])
    }

    pending = []
    for movie in movies:
        document = build_document(movie)
        digest = content_hash(document, embedder.signature)
        if existing_hashes.get(str(movie.douban_id)) == digest:
            continue  # 内容没变，不重复计费
        pending.append((movie, document, digest))

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        vectors = embedder.embed([document for _, document, _ in batch])
        collection.upsert(
            ids=[str(movie.douban_id) for movie, _, _ in batch],
            embeddings=vectors,
            documents=[document for _, document, _ in batch],
            metadatas=[
                {
                    "movie_id": movie.movie_id,
                    "title": movie.title,
                    "rating": movie.rating,
                    "content_hash": digest,
                }
                for movie, _, digest in batch
            ],
        )
        logger.info("已写入向量 %d/%d", min(start + BATCH_SIZE, len(pending)), len(pending))

    return {
        "total_movies": len(movies),
        "embedded": len(pending),
        "skipped_unchanged": len(movies) - len(pending),
        "embedder": embedder.signature,
    }


def index_ready() -> bool:
    try:
        return get_collection(create=False).count() > 0
    except Exception:
        return False


def index_embedder_signature() -> str | None:
    import json

    path = chroma_path() / SIGNATURE_FILE_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))["embedder"]
    except (OSError, ValueError, KeyError):
        return None


def search(query: str, embedder, top_k: int = 5) -> list[dict]:
    collection = get_collection(create=False)
    vector = embedder.embed([query])[0]
    result = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, max(collection.count(), 1)),
        include=["metadatas", "distances"],
    )
    matches = []
    for metadata, distance in zip(result["metadatas"][0], result["distances"][0]):
        matches.append({
            "movie_id": metadata["movie_id"],
            "title": metadata["title"],
            "rating": metadata["rating"],
            "score": round(1 - distance, 4),   # cosine 距离 → 相似度
        })
    return matches
