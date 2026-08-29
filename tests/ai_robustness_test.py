"""AI 摘要批处理健壮性测试。

要求：
1. 瞬时故障自动重试（指数退避，上限3次），重试后成功计入结果；
2. 单部电影最终失败必须跳过并继续处理后面的电影（不丢批处理进度），
   失败的电影仍处于"未摘要"状态，下次运行可续跑；
3. 每次成功调用把 response.usage 追加记录到 ai_usage.jsonl。
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://example.com")
    )


def make_response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        ),
    )


class StubClient:
    """按电影标题定制行为：脚本化返回成功或异常序列。"""

    def __init__(self, script: dict[str, list]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, *, messages, **_kwargs):
        prompt = messages[-1]["content"]
        title = next(t for t in self.script if t in prompt)
        self.calls.append(title)
        action = self.script[title].pop(0)
        if isinstance(action, Exception):
            raise action
        return make_response(action)


def setup_database(db_path: Path) -> None:
    schema = (PROJECT_ROOT / "database" / "schema.sql").read_text("utf-8")
    connection = sqlite3.connect(db_path)
    connection.executescript(schema)
    for index, title in enumerate(["电影甲", "电影乙", "电影丙"], start=1):
        connection.execute(
            """
            INSERT INTO movies (
                douban_id, title, rating, rating_count,
                introduction, introduction_source, source_url, collected_at
            ) VALUES (?, ?, 9.0, 100, '简介', 'inq', ?, '2026-07-26')
            """,
            (index, title, f"https://movie.douban.com/subject/{index}/"),
        )
    connection.commit()
    connection.close()


def test_ai_summary_robustness(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_BASE_URL", "https://example.com")
    monkeypatch.setenv("AI_MODEL", "m")
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        db_path = workdir / "test.db"
        setup_database(db_path)
        os.environ["SQLITE_DB_PATH"] = str(db_path)

        import ai_summary

        ai_summary.AI_SUMMARY_FILE = workdir / "ai_summaries.csv"
        ai_summary.AI_USAGE_FILE = workdir / "ai_usage.jsonl"

        stub = StubClient({
            "电影甲": [connection_error(), "甲的摘要"],       # 重试1次后成功
            "电影乙": [connection_error()] * 5,               # 持续失败
            "电影丙": ["丙的摘要"],                            # 直接成功
        })
        generated = ai_summary.generate_ai_summaries(
            limit=3,
            confirm_paid_run=True,
            client_factory=lambda: stub,
            retry_base_delay=0,
        )
        assert generated == 2, f"应成功2条（甲重试成功+丙），实际 {generated}"
        assert stub.calls.count("电影乙") == 3, (
            f"电影乙应重试到上限3次，实际 {stub.calls.count('电影乙')}"
        )
        assert stub.calls.count("电影丙") == 1, (
            "电影乙失败后必须继续处理电影丙，不能中断批处理"
        )

        connection = sqlite3.connect(db_path)
        titles = {
            row[0]
            for row in connection.execute(
                """
                SELECT m.title FROM ai_summaries AS s
                JOIN movies AS m ON m.movie_id = s.movie_id
                """
            ).fetchall()
        }
        connection.close()
        assert titles == {"电影甲", "电影丙"}, titles

        usage_lines = ai_summary.AI_USAGE_FILE.read_text("utf-8").splitlines()
        assert len(usage_lines) == 2, usage_lines
        assert json.loads(usage_lines[0])["total_tokens"] == 150

    print("AI_ROBUSTNESS_TEST=PASS")



