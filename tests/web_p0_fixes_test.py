"""光影智选 Web 层 P0/P1 复现测试。

1. flash 消息不允许互相覆盖（应追加，上限5条）；
2. 注册必须清空旧会话再写入（防会话固定攻击）；
3. CSRF 失效返回 flash + 跳转，而不是裸 JSON；
4. /movies?min_rating=abc 应回到正常页面，而不是英文 422 JSON；
5. 管理员保存正版链接：电影不存在时给 404 页面而不是外键 500；
   平台/URL 非法时 flash 提示而不是裸 JSON；
6. /health 真实探测数据库；
7. 未登录访问收藏页跳登录并提示。
"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "b-p0-fixes-test-secret")
os.environ["ADMIN_EMAILS"] = "admin@example.com"

from fastapi.testclient import TestClient  # noqa: E402
import web_app  # noqa: E402
from web_app import app, flash  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match, "页面中未找到 csrf 隐藏域"
    return match.group(1)


def register(client: TestClient, email: str) -> None:
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": "P0 Tester",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf": csrf_from(page.text),
        },
    )
    assert response.status_code == 200, response.status_code


def test_flash_appends() -> None:
    session: dict = {}
    fake_request = type("R", (), {"session": session})()
    flash(fake_request, "第一条")
    flash(fake_request, "第二条")
    texts = [item["text"] for item in session["messages"]]
    assert texts == ["第一条", "第二条"], f"flash 互相覆盖：{texts}"


def test_register_clears_session() -> None:
    with TestClient(app) as client:
        before = csrf_from(client.get("/login").text)
        register(client, "fixation@example.com")
        after = csrf_from(client.get("/movies").text)
        assert before != after, "注册未轮换会话（会话固定风险）"


def test_csrf_friendly(movie_id: int) -> None:
    with TestClient(app) as client:
        register(client, "csrf-b@example.com")
        response = client.post(
            f"/movies/{movie_id}/favorite",
            data={"csrf": "wrong"},
            headers={"referer": f"http://testserver/movies/{movie_id}"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.status_code
        follow = client.get(response.headers["location"])
        assert "请求已失效" in follow.text


def test_min_rating_garbage() -> None:
    with TestClient(app) as client:
        response = client.get("/movies", params={"min_rating": "abc"})
        assert response.status_code == 200, response.status_code
        assert "电影库" in response.text


def test_watch_link_errors(movie_id: int) -> None:
    with TestClient(app) as client:
        register(client, "admin@example.com")
        page = client.get(f"/movies/{movie_id}")
        token = csrf_from(page.text)
        # 电影不存在 → 404 页面
        missing = client.post(
            "/movies/999999/watch-links",
            data={"platform_name": "爱奇艺", "watch_url": "https://x.com", "csrf": token},
        )
        assert missing.status_code == 404, missing.status_code
        assert "没有找到" in missing.text
        # URL 非法 → flash 提示（页面），不是裸 JSON
        bad = client.post(
            f"/movies/{movie_id}/watch-links",
            data={"platform_name": "爱奇艺", "watch_url": "http://insecure", "csrf": token},
            follow_redirects=True,
        )
        assert "HTTPS" in bad.text and "detail" not in bad.text[:200]


def test_health_probes_database() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_favorites_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/favorites", follow_redirects=True)
        assert "请先登录" in response.text


