"""语义检索测试（离线，不依赖付费接口）。

用 HashingEmbedder（确定性、零费用）验证整条管线：
建索引幂等、检索排序、网页与 API 的可用/降级状态。
"""

import pytest

from web_database import SessionLocal
from web_models import Movie


@pytest.fixture
def chroma_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    return tmp_path


def seed_corpus() -> None:
    with SessionLocal() as database:
        database.add_all([
            Movie(
                douban_id=1, title="肖申克的救赎", rating=9.7,
                rating_count=3000000,
                introduction="监狱 越狱 希望让人自由",
                source_url="https://movie.douban.com/subject/1/",
                collected_at="2026-08-29",
            ),
            Movie(
                douban_id=2, title="美食总动员", rating=8.5,
                rating_count=800000,
                introduction="老鼠 厨房 做菜 美食",
                source_url="https://movie.douban.com/subject/2/",
                collected_at="2026-08-29",
            ),
            Movie(
                douban_id=3, title="海上钢琴师", rating=9.3,
                rating_count=1500000,
                introduction="钢琴 邮轮 音乐 大海",
                source_url="https://movie.douban.com/subject/3/",
                collected_at="2026-08-29",
            ),
        ])
        database.commit()


def test_build_index_idempotent_and_search(chroma_tmp) -> None:
    from embeddings import HashingEmbedder
    from semantic_index import build_index, index_embedder_signature, search

    seed_corpus()
    embedder = HashingEmbedder()
    report = build_index(embedder)
    assert report["embedded"] == 3 and report["skipped_unchanged"] == 0

    # 幂等：内容未变，重跑不重复向量化（真实场景=不重复计费）
    report = build_index(embedder)
    assert report["embedded"] == 0 and report["skipped_unchanged"] == 3

    assert index_embedder_signature() == embedder.signature
    matches = search("监狱 越狱 希望", embedder, top_k=3)
    assert matches[0]["title"] == "肖申克的救赎", matches


def test_search_page_and_api(chroma_tmp, client) -> None:
    from embeddings import HashingEmbedder
    from semantic_index import build_index

    seed_corpus()
    build_index(HashingEmbedder())

    page = client.get("/search", params={"q": "监狱 越狱 希望"})
    assert page.status_code == 200
    assert "肖申克的救赎" in page.text
    assert "字面匹配索引" in page.text, "哈希索引应向用户说明检索质量限制"

    api = client.get("/api/v1/search", params={"q": "监狱 越狱"}).json()
    assert api["results"][0]["title"] == "肖申克的救赎", api


def test_search_without_index_degrades(chroma_tmp, client) -> None:
    page = client.get("/search", params={"q": "越狱"})
    assert page.status_code == 200
    assert "语义索引尚未构建" in page.text

    api = client.get("/api/v1/search", params={"q": "越狱"})
    assert api.status_code == 503
    assert api.json()["error"]["code"] == "service_unavailable"
