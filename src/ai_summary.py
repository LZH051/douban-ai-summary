import logging
import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Callable

from db import connect_to_database, load_dotenv_if_available
from paths import AI_SUMMARY_FILE, AI_USAGE_FILE, ensure_directories

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30.0


def is_transient_error(error: Exception) -> bool:
    """网络/超时/限流/服务端 5xx 才值得重试，4xx 配置类错误重试无意义。"""
    import openai

    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(error, openai.RateLimitError):
        return True
    if isinstance(error, openai.APIStatusError):
        return error.status_code >= 500
    return False


def call_with_retry(
    request: Callable[[], object], retry_base_delay: float = 2.0
) -> object:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return request()
        except Exception as error:
            if not is_transient_error(error) or attempt == MAX_ATTEMPTS:
                raise
            delay = retry_base_delay * (2 ** (attempt - 1))
            logger.warning(
                "AI 调用第 %d/%d 次失败（%s），%.1f 秒后重试",
                attempt, MAX_ATTEMPTS, type(error).__name__, delay,
            )
            time.sleep(delay)
    raise RuntimeError("unreachable")


def record_usage(model: str, usage: object) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
    AI_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AI_USAGE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(
        "本次调用消耗 token：输入 %s / 输出 %s / 合计 %s",
        entry["prompt_tokens"], entry["completion_tokens"], entry["total_tokens"],
    )


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
    client_factory: Callable[[], object] | None = None,
    retry_base_delay: float = 2.0,
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
    if client_factory is None:
        from openai import OpenAI

        def client_factory() -> object:
            # max_retries=0：重试策略由 call_with_retry 统一控制，避免叠加
            return OpenAI(
                api_key=api_key,
                base_url=base_url,
                max_retries=0,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

    client = client_factory()
    generated_count = 0
    failed_titles: list[str] = []
    for index, movie in enumerate(movies, start=1):
        logger.info(f"生成摘要 {index}/{len(movies)}：{movie['title']}")
        # 单部失败只跳过这一部，批处理继续；失败的电影仍是"未摘要"
        # 状态，下次运行会被 LEFT JOIN 重新选中，天然支持断点续跑
        try:
            response = call_with_retry(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是严谨的电影信息摘要助手。"},
                        {"role": "user", "content": build_prompt(movie)},
                    ],
                    temperature=0.3,
                ),
                retry_base_delay=retry_base_delay,
            )
        except Exception:
            logger.exception(f"《{movie['title']}》摘要生成失败，跳过继续")
            failed_titles.append(movie["title"])
            continue

        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            logger.error(f"模型返回空摘要：《{movie['title']}》，跳过继续")
            failed_titles.append(movie["title"])
            continue
        if getattr(response, "usage", None) is not None:
            record_usage(model, response.usage)

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
    if failed_titles:
        logger.warning(
            "本次失败 %d 部（下次运行会自动重新选中）：%s",
            len(failed_titles), "、".join(failed_titles),
        )
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
