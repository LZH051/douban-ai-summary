import csv

from db import connect_to_database
from init_database import initialize_database
from paths import CLEAN_DATA_FILE


def load_movies() -> tuple[int, int]:
    if not CLEAN_DATA_FILE.exists():
        raise FileNotFoundError(f"未找到清洗数据：{CLEAN_DATA_FILE}")

    initialize_database()
    with CLEAN_DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies")
        before_count = cursor.fetchone()[0]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO movies (
                douban_id, title, rating, rating_count,
                introduction, source_url, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    int(row["douban_id"]),
                    row["title"],
                    float(row["rating"]),
                    int(row["rating_count"]),
                    row["introduction"],
                    row["source_url"],
                    row["collected_at"],
                )
                for row in rows
            ],
        )
        connection.commit()
        cursor.execute("SELECT COUNT(*) FROM movies")
        after_count = cursor.fetchone()[0]
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    inserted_count = after_count - before_count
    skipped_count = len(rows) - inserted_count
    print(f"新增电影：{inserted_count} 条")
    print(f"跳过已存在电影：{skipped_count} 条")
    return inserted_count, skipped_count


if __name__ == "__main__":
    load_movies()
