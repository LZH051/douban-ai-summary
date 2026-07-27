import argparse
import csv

from db import connect_to_database, get_database_path
from paths import CLEAN_DATA_FILE, RAW_DATA_FILE


def count_csv_rows(path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return sum(1 for _ in csv.DictReader(file))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验收项目B SQLite版")
    parser.add_argument("--expected-min", type=int, default=20)
    parser.add_argument("--require-ai", action="store_true")
    return parser.parse_args()


def verify_project(expected_min: int = 20, require_ai: bool = False) -> None:
    required_tables = {"movies", "ai_summaries"}
    raw_count = count_csv_rows(RAW_DATA_FILE)
    clean_count = count_csv_rows(CLEAN_DATA_FILE)

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        table_names = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) FROM movies")
        movie_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM ai_summaries")
        summary_count = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT douban_id FROM movies
                GROUP BY douban_id HAVING COUNT(*) > 1
            )
            """
        )
        duplicate_count = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM movies
            WHERE title = '' OR introduction = '' OR source_url = ''
               OR rating IS NULL OR rating_count IS NULL
            """
        )
        missing_count = cursor.fetchone()[0]
    finally:
        connection.close()

    assert required_tables.issubset(table_names), "缺少 SQLite 数据表"
    assert raw_count >= expected_min, "采集数据数量不足"
    assert clean_count == movie_count, "清洗数据与 SQLite 数量不一致"
    assert duplicate_count == 0, "数据库中存在重复电影"
    assert missing_count == 0, "数据库中存在缺失字段"
    if require_ai:
        assert summary_count >= 5, "AI 摘要不足5条"

    print(f"SQLite：{get_database_path()}")
    print(f"数据库表：{', '.join(sorted(required_tables))}")
    print(f"原始数据：{raw_count} 条")
    print(f"清洗数据：{clean_count} 条")
    print(f"数据库电影：{movie_count} 条")
    print(f"AI 摘要：{summary_count} 条")
    print("重复数据检查：通过")
    print("字段完整性检查：通过")
    print("项目B SQLite 验收：通过")


if __name__ == "__main__":
    arguments = parse_args()
    verify_project(arguments.expected_min, arguments.require_ai)
