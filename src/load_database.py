import csv

from db import connect_to_database
from init_database import initialize_database
from paths import CLEAN_DATA_FILE


def load_movies() -> tuple[int, int]:
    """新增电影；豆瓣 ID 已存在时更新其最新字段。"""
    if not CLEAN_DATA_FILE.exists():
        raise FileNotFoundError(f"未找到清洗数据：{CLEAN_DATA_FILE}")

    initialize_database()
    with CLEAN_DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    values = [
        (
            int(row["douban_id"]),
            row["title"],
            float(row["rating"]),
            int(row["rating_count"]),
            row["introduction"],
            row.get("introduction_source", "unknown"),
            row["source_url"],
            row["collected_at"],
        )
        for row in rows
    ]

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        existing_ids = {
            row[0] for row in cursor.execute("SELECT douban_id FROM movies").fetchall()
        }
        cursor.executemany(
            """
            INSERT INTO movies (
                douban_id, title, rating, rating_count,
                introduction, introduction_source, source_url, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(douban_id) DO UPDATE SET
                title = excluded.title,
                rating = excluded.rating,
                rating_count = excluded.rating_count,
                introduction = excluded.introduction,
                introduction_source = excluded.introduction_source,
                source_url = excluded.source_url,
                collected_at = excluded.collected_at
            """,
            values,
        )
        connection.commit()
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    updated_count = sum(1 for row in rows if int(row["douban_id"]) in existing_ids)
    inserted_count = len(rows) - updated_count
    print(f"新增电影：{inserted_count} 条")
    print(f"更新已有电影：{updated_count} 条")
    return inserted_count, updated_count


if __name__ == "__main__":
    load_movies()
