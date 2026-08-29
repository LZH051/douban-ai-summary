"""安全加固测试：登录限流、CSP 响应头、收藏页禁缓存。"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "b-security-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import app  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match
    return match.group(1)


def register(client: TestClient, email: str) -> None:
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": "Sec Tester", "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf": csrf_from(page.text),
        },
    )
    assert response.status_code == 200


def test_login_rate_limit() -> None:
    email = "b-rate@example.com"
    with TestClient(app) as client:
        register(client, email)
    with TestClient(app) as client:
        for _ in range(5):
            page = client.get("/login")
            response = client.post(
                "/login",
                data={"email": email, "password": "Wrong!",
                      "csrf": csrf_from(page.text)},
            )
            assert response.status_code == 401, response.status_code
        page = client.get("/login")
        blocked = client.post(
            "/login",
            data={"email": email, "password": "SecurePass123!",
                  "csrf": csrf_from(page.text)},
        )
        assert blocked.status_code == 429, blocked.status_code
        assert "尝试次数过多" in blocked.text


def test_headers() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        assert "content-security-policy" in home.headers
        assert "default-src 'self'" in home.headers["content-security-policy"]
        register(client, "b-headers@example.com")
        favorites = client.get("/favorites")
        assert favorites.headers.get("cache-control") == "no-store"


def main() -> None:
    test_login_rate_limit()
    test_headers()
    print("B_SECURITY_TEST=PASS")


if __name__ == "__main__":
    main()
