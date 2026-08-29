"""AI 摘要的 LangChain 实现（与手写版 ai_summary.py 并存）。

与手写版行为对齐：同一份 prompt 语义、超时 30s、瞬时故障最多
3 次重试、单条失败跳过续跑、按 douban_id 缓存不重复计费。
差异与取舍见 docs/langchain_notes.md。

用法：python src/ai_summary_lc.py --limit 5 --confirm-paid-run
"""

import argparse
import logging

from ai_summary import (
    build_prompt,
    export_summaries,
    fetch_unsummarized_movies,
    get_ai_config,
)
from db import connect_to_database

logger = logging.getLogger(__name__)


def build_chain():
    """prompt | llm | 解析器。重试交给 LangChain 的 with_retry。"""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    api_key, base_url, model = get_ai_config()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是严谨的电影信息摘要助手。"),
        ("human", "{movie_prompt}"),
    ])
    llm = ChatOpenAI(
        model=model, api_key=api_key, base_url=base_url,
        temperature=0.3, timeout=30, max_retries=0,
    ).with_retry(
        stop_after_attempt=3,
        wait_exponential_jitter=True,
    )
    return prompt | llm | StrOutputParser(), model


def generate_ai_summaries_lc(
    limit: int = 5,
    confirm_paid_run: bool = False,
    chain=None,
    model_name: str = "langchain-stub",
) -> int:
    if not confirm_paid_run:
        raise RuntimeError("AI 调用可能产生费用，尚未获得明确确认。")
    if not 1 <= limit <= 10:
        raise ValueError("单次 AI 摘要数量必须在1～10之间")

    movies = fetch_unsummarized_movies(limit)
    if not movies:
        logger.info("没有待生成摘要的电影")
        export_summaries()
        return 0

    if chain is None:
        chain, model_name = build_chain()

    generated_count = 0
    failed_titles: list[str] = []
    for index, movie in enumerate(movies, start=1):
        logger.info("生成摘要(LC) %d/%d：%s", index, len(movies), movie["title"])
        try:
            summary = chain.invoke(
                {"movie_prompt": build_prompt(movie)}
            ).strip()
        except Exception:
            logger.exception("《%s》摘要生成失败，跳过继续", movie["title"])
            failed_titles.append(movie["title"])
            continue
        if not summary:
            logger.error("模型返回空摘要：《%s》，跳过继续", movie["title"])
            failed_titles.append(movie["title"])
            continue

        connection = connect_to_database()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ai_summaries (
                    movie_id, summary, model_name
                ) VALUES (?, ?, ?)
                """,
                (movie["movie_id"], summary, f"langchain:{model_name}"),
            )
            connection.commit()
            generated_count += cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    export_summaries()
    logger.info("本次新增 AI 摘要(LC)：%d 条", generated_count)
    if failed_titles:
        logger.warning(
            "本次失败 %d 部（下次运行会自动重新选中）：%s",
            len(failed_titles), "、".join(failed_titles),
        )
    return generated_count


def main() -> None:
    from logging_setup import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description="生成电影 AI 摘要（LangChain 版）")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=5)
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")
    generate_ai_summaries_lc(args.limit, confirm_paid_run=True)


if __name__ == "__main__":
    main()
