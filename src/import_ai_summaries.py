import csv

from db import connect_to_database
from init_database import initialize_database
from paths import AI_SUMMARY_FILE


def import_existing_summaries() -> tuple[int, int]:
    """把已有摘要 CSV 导入 SQLite，不调用任何 AI 接口。"""
    if not AI_SUMMARY_FILE.exists():
        raise FileNotFoundError(f"未找到摘要文件：{AI_SUMMARY_FILE}")
    initialize_database()
    with AI_SUMMARY_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    inserted = 0
    unmatched = 0
    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        for row in rows:
            cursor.execute(
                "SELECT movie_id FROM movies WHERE title = ?",
                (row["title"],),
            )
            movie = cursor.fetchone()
            if movie is None:
                unmatched += 1
                continue
            cursor.execute(
                """
                INSERT OR IGNORE INTO ai_summaries (
                    movie_id, summary, model_name, created_at
                )
                VALUES (?, ?, ?, COALESCE(NULLIF(?, ''), CURRENT_TIMESTAMP))
                """,
                (
                    movie["movie_id"],
                    row["summary"],
                    row["model_name"],
                    row.get("created_at", ""),
                ),
            )
            inserted += cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"导入已有 AI 摘要：{inserted} 条")
    print(f"未匹配电影：{unmatched} 条")
    print("本步骤未调用 AI 接口")
    return inserted, unmatched


if __name__ == "__main__":
    import_existing_summaries()
