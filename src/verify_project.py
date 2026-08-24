import argparse
import csv

from db import connect_to_database, get_database_path
from paths import CLEAN_DATA_FILE, RAW_DATA_FILE


def read_csv_rows(path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验收项目B SQLite版")
    parser.add_argument("--expected-min", type=int, default=20)
    parser.add_argument("--require-ai", action="store_true")
    return parser.parse_args()


def verify_project(expected_min: int = 20, require_ai: bool = False) -> None:
    required_tables = {"movies", "ai_summaries"}
    raw_rows = read_csv_rows(RAW_DATA_FILE)
    clean_rows = read_csv_rows(CLEAN_DATA_FILE)
    clean_ids = {int(row["douban_id"]) for row in clean_rows}

    connection = connect_to_database()
    try:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        movie_rows = connection.execute(
            "SELECT douban_id FROM movies"
        ).fetchall()
        database_ids = {row[0] for row in movie_rows}
        movie_count = len(movie_rows)
        summary_count = connection.execute(
            "SELECT COUNT(*) FROM ai_summaries"
        ).fetchone()[0]
        duplicate_count = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT douban_id FROM movies
                GROUP BY douban_id HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        missing_count = connection.execute(
            """
            SELECT COUNT(*) FROM movies
            WHERE TRIM(title) = '' OR TRIM(introduction) = ''
               OR TRIM(source_url) = '' OR rating IS NULL
               OR rating_count IS NULL
            """
        ).fetchone()[0]
        orphan_summary_count = connection.execute(
            """
            SELECT COUNT(*) FROM ai_summaries AS s
            LEFT JOIN movies AS m ON m.movie_id = s.movie_id
            WHERE m.movie_id IS NULL
            """
        ).fetchone()[0]
    finally:
        connection.close()

    require(required_tables.issubset(table_names), "缺少 SQLite 数据表")
    require(len(raw_rows) >= expected_min, "采集数据数量不足")
    require(clean_ids.issubset(database_ids), "部分清洗电影尚未写入 SQLite")
    require(duplicate_count == 0, "数据库中存在重复电影")
    require(missing_count == 0, "数据库中存在缺失字段")
    require(orphan_summary_count == 0, "存在无法关联电影的AI摘要")
    if require_ai:
        require(summary_count >= 5, "AI 摘要不足5条")

    manual_extra = movie_count - len(clean_ids)
    print(f"SQLite：{get_database_path()}")
    print(f"数据库表：{', '.join(sorted(required_tables))}")
    print(f"原始数据：{len(raw_rows)} 条")
    print(f"清洗数据：{len(clean_rows)} 条")
    print(f"数据库电影：{movie_count} 条（额外手动记录：{manual_extra} 条）")
    print(f"AI 摘要：{summary_count} 条")
    print("重复数据检查：通过")
    print("字段完整性检查：通过")
    print("AI摘要外键检查：通过")
    print("项目B SQLite 验收：通过")


if __name__ == "__main__":
    arguments = parse_args()
    verify_project(arguments.expected_min, arguments.require_ai)
