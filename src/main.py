import argparse

from ai_summary import generate_ai_summaries
from cleaner import clean_data
from load_database import load_movies
from scraper import scrape_top250


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="豆瓣电影Top250 SQLite 数据分析与 AI 摘要工具"
    )
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=5.0)
    parser.add_argument("--with-ai", action="store_true")
    parser.add_argument("--ai-limit", type=int, default=5)
    parser.add_argument("--confirm-paid-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.with_ai and not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")

    print("步骤 1/3：低频采集豆瓣电影Top250")
    scrape_top250(args.pages, args.delay_min, args.delay_max)
    print("\n步骤 2/3：清洗与去重")
    clean_data()
    print("\n步骤 3/3：写入 SQLite")
    load_movies()

    if args.with_ai:
        print("\n生成 AI 摘要")
        generate_ai_summaries(args.ai_limit)
    else:
        print("\nSQLite 数据流程完成，未调用付费 AI 接口。")


if __name__ == "__main__":
    main()
