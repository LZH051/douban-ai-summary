"""pytest 共享配置（光影智选）。

环境变量必须在导入 web_app 之前设置：engine 在 web_database
导入期就按 DATABASE_URL 创建。conftest 先于所有测试模块加载。
"""

import os
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_TMP_DIR = tempfile.mkdtemp(prefix="douban-pytest-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DIR}/web.db")
os.environ.setdefault("SESSION_SECRET", "pytest-session-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import web_app  # noqa: E402
from web_database import Base, SessionLocal, engine  # noqa: E402
from web_models import Movie  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """每个测试独享干净数据库（movies 是全局数据，最容易互相污染）。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(web_app.app) as test_client:
        yield test_client


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match, "页面中未找到 csrf 隐藏域"
    return match.group(1)


def register(client: TestClient, email: str = "pytest@example.com") -> None:
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": "Pytest User",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf": csrf_from(page.text),
        },
    )
    assert response.status_code == 200, response.status_code


@pytest.fixture
def user_client(client):
    register(client)
    return client


def seed_movie(douban_id: int = 42, title: str = "测试电影") -> int:
    with SessionLocal() as database:
        movie = Movie(
            douban_id=douban_id, title=title, rating=9.0,
            rating_count=1000, introduction="用于网站测试的电影简介。",
            source_url=f"https://movie.douban.com/subject/{douban_id}/",
            collected_at="2026-08-29",
        )
        database.add(movie)
        database.commit()
        database.refresh(movie)
        return movie.movie_id


@pytest.fixture
def movie_id() -> int:
    return seed_movie()
