"""任务三测试：判分规则、离线回放、LangChain 链路（桩）。"""

import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "evals"))

from run_eval import CACHE_FILE, CASES_FILE, evaluate, load_jsonl, score_summary

CASE = {
    "douban_id": 1,
    "title": "肖申克的救赎",
    "rating": "9.7",
    "rating_count": "3324390",
    "introduction": "希望让人自由。",
}


def test_scoring_rules() -> None:
    good = "《肖申克的救赎》讲述银行家安迪在监狱中坚守希望、最终重获自由的故事。"
    assert score_summary(CASE, good)["passed"]

    def failed_rules(output: str) -> set[str]:
        result = score_summary(CASE, output)
        return {c["rule"] for c in result["checks"] if not c["ok"]}

    assert "非空" in failed_rules("")
    assert "长度≤80字" in failed_rules("肖申克的救赎" + "很" * 100)
    assert "包含片名" in failed_rules("一部关于监狱与希望的电影。")
    assert "不复述评分" in failed_rules("肖申克的救赎评分9.7，非常好看。")
    assert "不复述评价人数" in failed_rules("肖申克的救赎有3324390人评价。")
    assert "无臆测词" in failed_rules("肖申克的救赎可能是最好的电影。")


def test_evaluate_counts_missing() -> None:
    cases = [CASE, {**CASE, "douban_id": 2, "title": "另一部"}]
    outputs = {1: {"output": "《肖申克的救赎》：监狱中的希望。", "engine": "x"}}
    report = evaluate(cases, outputs)
    assert report["evaluated"] == 1 and report["missing"] == 1
    assert report["passed"] == 1 and report["pass_rate"] == 1.0


def test_cached_replay_on_repo_data() -> None:
    """仓库自带的评测集 + 真实历史输出：离线回放必须可用。"""
    cases = load_jsonl(CASES_FILE)
    outputs = {item["douban_id"]: item for item in load_jsonl(CACHE_FILE)}
    assert len(cases) == 10
    report = evaluate(cases, outputs)
    assert report["evaluated"] >= 5
    assert report["passed"] == report["evaluated"], (
        "已缓存的真实输出应全部通过判分"
    )


def _seed_summary_database(db_path: Path) -> None:
    schema = (PROJECT_ROOT / "database" / "schema.sql").read_text("utf-8")
    connection = sqlite3.connect(db_path)
    connection.executescript(schema)
    for index, title in enumerate(["电影甲", "电影乙"], start=1):
        connection.execute(
            """
            INSERT INTO movies (
                douban_id, title, rating, rating_count,
                introduction, introduction_source, source_url, collected_at
            ) VALUES (?, ?, 9.0, 100, '简介', 'inq', ?, '2026-08-29')
            """,
            (index, title, f"https://movie.douban.com/subject/{index}/"),
        )
    connection.commit()
    connection.close()


def test_langchain_pipeline_with_stub_chain(monkeypatch) -> None:
    from langchain_core.runnables import RunnableLambda

    import ai_summary
    import ai_summary_lc

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        db_path = workdir / "test.db"
        _seed_summary_database(db_path)
        monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
        monkeypatch.setattr(
            ai_summary, "AI_SUMMARY_FILE", workdir / "ai_summaries.csv"
        )

        chain = RunnableLambda(
            lambda payload: f"桩摘要：{payload['movie_prompt'][:0]}电影一句话。"
        )
        generated = ai_summary_lc.generate_ai_summaries_lc(
            limit=5, confirm_paid_run=True, chain=chain, model_name="stub",
        )
        assert generated == 2

        # 缓存机制与手写版共享：已有摘要的电影不会再被选中
        generated = ai_summary_lc.generate_ai_summaries_lc(
            limit=5, confirm_paid_run=True, chain=chain, model_name="stub",
        )
        assert generated == 0

        connection = sqlite3.connect(db_path)
        rows = connection.execute(
            "SELECT model_name, COUNT(*) FROM ai_summaries GROUP BY model_name"
        ).fetchall()
        connection.close()
        assert rows == [("langchain:stub", 2)], rows
