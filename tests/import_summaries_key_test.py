"""P0-4 复现测试：摘要导入必须用 douban_id 关联，不能用 title。

movies.title 没有唯一约束，Top250 中同名不同片（翻拍/同名不同年份）
是常见情况；douban_id 才是稳定的自然键。
"""

import csv
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def setup_database(db_path: Path) -> None:
    schema = (PROJECT_ROOT / "database" / "schema.sql").read_text("utf-8")
    connection = sqlite3.connect(db_path)
    connection.executescript(schema)
    # 两部同名电影，douban_id 不同
    for douban_id, url in ((1111, "https://movie.douban.com/subject/1111/"),
                           (2222, "https://movie.douban.com/subject/2222/")):
        connection.execute(
            """
            INSERT INTO movies (
                douban_id, title, rating, rating_count,
                introduction, introduction_source, source_url, collected_at
            ) VALUES (?, '小丑', 8.7, 1000000, '简介', 'inq', ?, '2026-07-26')
            """,
            (douban_id, url),
        )
    connection.commit()
    connection.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        db_path = workdir / "test.db"
        setup_database(db_path)
        os.environ["SQLITE_DB_PATH"] = str(db_path)

        import import_ai_summaries

        csv_path = workdir / "ai_summaries.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "douban_id", "title", "summary", "model_name", "created_at"
                ],
            )
            writer.writeheader()
            writer.writerow({
                "douban_id": "2222",
                "title": "小丑",
                "summary": "2019年版摘要",
                "model_name": "m",
                "created_at": "",
            })
        import_ai_summaries.AI_SUMMARY_FILE = csv_path
        inserted, unmatched = import_ai_summaries.import_existing_summaries()
        assert inserted == 1 and unmatched == 0, (inserted, unmatched)

        connection = sqlite3.connect(db_path)
        rows = connection.execute(
            """
            SELECT m.douban_id FROM ai_summaries AS s
            JOIN movies AS m ON m.movie_id = s.movie_id
            """
        ).fetchall()
        connection.close()
        assert rows == [(2222,)], (
            f"摘要挂错了电影：应关联 douban_id=2222，实际 {rows}"
        )
    print("IMPORT_SUMMARIES_KEY_TEST=PASS")


if __name__ == "__main__":
    main()
