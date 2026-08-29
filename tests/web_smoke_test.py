import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
temporary_database = Path(tempfile.gettempdir()) / "douban_web_smoke.db"
os.environ["DATABASE_URL"] = f"sqlite:///{temporary_database.as_posix()}"
os.environ["SESSION_SECRET"] = "test-session-secret"

from fastapi.testclient import TestClient  # noqa: E402
from web_app import app  # noqa: E402
from web_database import Base, SessionLocal, engine  # noqa: E402
from web_models import Movie  # noqa: E402


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
with SessionLocal() as database:
    database.add(Movie(
        douban_id=1292052, title="测试电影", rating=9.6,
        rating_count=1000, introduction="用于网站测试的电影。",
        source_url="https://movie.douban.com/subject/1292052/",
        collected_at="2026-08-24",
    ))
    database.commit()

with TestClient(app) as client:
    assert client.get("/").status_code == 200
    assert "测试电影" in client.get("/movies").text
    detail = client.get("/movies/1")
    assert detail.status_code == 200
    assert "在爱奇艺搜索" in detail.text
    assert "search.bilibili.com/all" in detail.text
    assert "不代表平台一定拥有该电影版权" in detail.text
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}

print("WEB_SMOKE_TEST=PASS")
