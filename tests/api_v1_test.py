"""光影智选 /api/v1 测试：公开检索、详情、收藏、统一错误封装。"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "b-api-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import app  # noqa: E402
from web_database import SessionLocal  # noqa: E402
from web_models import AISummary, Movie  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match
    return match.group(1)


def seed() -> int:
    with SessionLocal() as database:
        first = None
        for index in range(1, 16):
            movie = Movie(
                douban_id=1000 + index,
                title=f"API电影{index}",
                rating=8.0 + index * 0.1,
                rating_count=1000 * index,
                introduction=f"简介{index}",
                source_url=f"https://movie.douban.com/subject/{1000 + index}/",
                collected_at="2026-08-29",
            )
            database.add(movie)
            database.flush()
            if first is None:
                first = movie.movie_id
        database.add(AISummary(
            movie_id=first, summary="API摘要", model_name="m"
        ))
        database.commit()
        return first


def test_api_v1_endpoints() -> None:
    with TestClient(app) as client:
        first_id = seed()

        # 公开列表：分页 + 搜索 + 评分筛选
        page1 = client.get("/api/v1/movies", params={"page_size": 10}).json()
        assert page1["total"] == 15 and len(page1["items"]) == 10, page1["total"]
        assert page1["pages"] == 2
        search = client.get("/api/v1/movies", params={"q": "API电影15"}).json()
        assert search["total"] == 1
        assert search["items"][0]["rating"] == 9.5
        rated = client.get("/api/v1/movies", params={"min_rating": 9.0}).json()
        assert rated["total"] == 6, rated["total"]

        # 详情：含摘要；404 统一封装
        detail = client.get(f"/api/v1/movies/{first_id}").json()
        assert detail["ai_summary"] == "API摘要", detail
        missing = client.get("/api/v1/movies/999999")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"

        # 参数越界：422 封装
        bad = client.get("/api/v1/movies", params={"page_size": 500})
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "validation_error"

        # 收藏需要登录
        anon = client.post(f"/api/v1/movies/{first_id}/favorite")
        assert anon.status_code == 401
        assert anon.json()["error"]["code"] == "unauthorized"

        page = client.get("/register")
        client.post(
            "/register",
            data={
                "username": "API Tester", "email": "b-api@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "csrf": csrf_from(page.text),
            },
        )
        added = client.post(f"/api/v1/movies/{first_id}/favorite").json()
        assert added["favorite"] is True, added
        favorites = client.get("/api/v1/favorites").json()
        assert favorites["total"] == 1
        assert favorites["items"][0]["movie_id"] == first_id
        removed = client.post(f"/api/v1/movies/{first_id}/favorite").json()
        assert removed["favorite"] is False

    print("B_API_V1_TEST=PASS")


if __name__ == "__main__":
    test_api_v1_endpoints()
