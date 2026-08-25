import logging
import argparse

from interactive import run_interactive

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="豆瓣电影Top250 SQLite 数据分析与 AI 摘要工具"
    )
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=5.0)
    parser.add_argument("--with-ai", action="store_true")
    parser.add_argument("--ai-limit", type=int, choices=range(1, 11), default=5)
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interactive:
        run_interactive()
        return
    if args.with_ai and not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")

    # 交互模式不需要网页采集依赖，因此仅在执行采集流程时导入。
    from ai_summary import generate_ai_summaries
    from cleaner import clean_data
    from load_database import load_movies
    from scraper import scrape_top250

    logger.info("步骤 1/3：低频采集豆瓣电影Top250")
    scrape_top250(args.pages, args.delay_min, args.delay_max)
    logger.info("\n步骤 2/3：清洗与去重")
    clean_data()
    logger.info("\n步骤 3/3：写入或更新 SQLite")
    load_movies()

    if args.with_ai:
        logger.info("\n生成 AI 摘要")
        generate_ai_summaries(
            args.ai_limit, confirm_paid_run=args.confirm_paid_run
        )
    else:
        logger.info("\nSQLite 数据流程已完成，未调用付费 AI 接口。")


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    main()
