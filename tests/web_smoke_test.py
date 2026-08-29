"""网页冒烟测试（pytest 版）。

原版把建库/造数写在模块导入期、并硬编码 /movies/1（依赖自增主键
恰好为 1）；现在使用 conftest 的临时库与 movie_id fixture。
"""


def test_web_smoke(client, movie_id) -> None:
    assert client.get("/").status_code == 200
    assert "测试电影" in client.get("/movies").text

    detail = client.get(f"/movies/{movie_id}")
    assert detail.status_code == 200
    assert "在爱奇艺搜索" in detail.text
    assert "search.bilibili.com/all" in detail.text
    assert "不代表平台一定拥有该电影版权" in detail.text

    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
