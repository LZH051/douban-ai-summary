import logging
import argparse
import csv
import os

from db import connect_to_database, load_dotenv_if_available
from paths import AI_SUMMARY_FILE, ensure_directories

logger = logging.getLogger(__name__)


def get_ai_config() -> tuple[str, str, str]:
    load_dotenv_if_available()
    values = {
        "AI_API_KEY": os.getenv("AI_API_KEY", "").strip(),
        "AI_BASE_URL": os.getenv("AI_BASE_URL", "").strip(),
        "AI_MODEL": os.getenv("AI_MODEL", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("AI 配置不完整：" + ", ".join(missing))
    return values["AI_API_KEY"], values["AI_BASE_URL"], values["AI_MODEL"]


def build_prompt(movie: dict) -> str:
    return f"""请根据下面的豆瓣电影信息生成简洁摘要：

电影名称：{movie['title']}
评分：{movie['rating']}
评价人数：{movie['rating_count']}
简介：{movie['introduction']}

要求：使用中文，控制在80字以内，只根据给出的信息总结，不虚构剧情，
不要重复输出评分和评价人数。
"""


def fetch_unsummarized_movies(
    limit: int,
    movie_ids: list[int] | None = None,
) -> list[dict]:
    where = "WHERE s.summary_id IS NULL"
    parameters: list[int] = []
    if movie_ids:
        placeholders = ", ".join("?" for _ in movie_ids)
        where += f" AND m.movie_id IN ({placeholders})"
        parameters.extend(movie_ids)
    parameters.append(limit)

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT m.movie_id, m.title, m.rating,
                   m.rating_count, m.introduction
            FROM movies AS m
            LEFT JOIN ai_summaries AS s ON s.movie_id = m.movie_id
            {where}
            ORDER BY m.rating DESC, m.rating_count DESC
            LIMIT ?
            """,
            parameters,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def export_summaries() -> None:
    ensure_directories()
    connection = connect_to_database()
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT m.douban_id, m.title, s.summary,
                       s.model_name, s.created_at
                FROM ai_summaries AS s
                JOIN movies AS m ON m.movie_id = s.movie_id
                ORDER BY s.summary_id
                """
            ).fetchall()
        ]
    finally:
        connection.close()

    with AI_SUMMARY_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "douban_id", "title", "summary", "model_name", "created_at"
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def generate_ai_summaries(
    limit: int = 5,
    confirm_paid_run: bool = False,
    movie_ids: list[int] | None = None,
) -> int:
    if not confirm_paid_run:
        raise RuntimeError("AI 调用可能产生费用，尚未获得明确确认。")
    if not 1 <= limit <= 10:
        raise ValueError("单次 AI 摘要数量必须在1～10之间")

    movies = fetch_unsummarized_movies(limit, movie_ids)
    if not movies:
        logger.info("没有待生成摘要的电影")
        export_summaries()
        return 0

    api_key, base_url, model = get_ai_config()
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
        timeout=30.0,
    )
    generated_count = 0
    for index, movie in enumerate(movies, start=1):
        logger.info(f"生成摘要 {index}/{len(movies)}：{movie['title']}")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是严谨的电影信息摘要助手。"},
                {"role": "user", "content": build_prompt(movie)},
            ],
            temperature=0.3,
        )
        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            raise RuntimeError(f"模型没有返回摘要：{movie['title']}")

        connection = connect_to_database()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ai_summaries (
                    movie_id, summary, model_name
                ) VALUES (?, ?, ?)
                """,
                (movie["movie_id"], summary, model),
            )
            connection.commit()
            generated_count += cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    export_summaries()
    logger.info(f"本次新增 AI 摘要：{generated_count} 条")
    return generated_count


def main() -> None:
    parser = argparse.ArgumentParser(description="生成电影 AI 摘要")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=5)
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")
    generate_ai_summaries(args.limit, confirm_paid_run=True)


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    main()
