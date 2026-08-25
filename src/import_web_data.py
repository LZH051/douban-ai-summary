"""把清洗后的电影 CSV 与 AI 摘要 CSV 导入网页数据库（README 所述脚本）。

- 目标库由 DATABASE_URL 决定：本地默认 SQLite，配置 Neon 直连
  字符串后即导入线上 PostgreSQL；
- 电影按 douban_id upsert，摘要按 douban_id 关联且一部电影只保留
  一条，支持重复运行；
- 全程不调用任何 AI 接口。
"""

import argparse
import csv
import logging
from datetime import datetime

from sqlalchemy import select

from paths import AI_SUMMARY_FILE, CLEAN_DATA_FILE
from web_database import Base, SessionLocal, engine
from web_models import AISummary, Movie

logger = logging.getLogger(__name__)


def parse_created_at(value: str) -> datetime | None:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def read_csv(path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"未找到文件：{path}")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def import_web_data() -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    movie_rows = read_csv(CLEAN_DATA_FILE)
    summary_rows = read_csv(AI_SUMMARY_FILE)

    result = {
        "movies_inserted": 0,
        "movies_updated": 0,
        "summaries_inserted": 0,
        "summaries_skipped": 0,
    }

    with SessionLocal() as session:
        for row in movie_rows:
            douban_id = int(row["douban_id"])
            movie = session.scalar(
                select(Movie).where(Movie.douban_id == douban_id)
            )
            if movie is None:
                movie = Movie(douban_id=douban_id)
                session.add(movie)
                result["movies_inserted"] += 1
            else:
                result["movies_updated"] += 1
            movie.title = row["title"]
            movie.rating = float(row["rating"])
            movie.rating_count = int(row["rating_count"])
            movie.introduction = row["introduction"]
            movie.source_url = row["source_url"]
            movie.collected_at = row["collected_at"]

        session.flush()

        for row in summary_rows:
            douban_id = (row.get("douban_id") or "").strip()
            if not douban_id:
                logger.warning(
                    f"摘要缺少 douban_id，跳过：《{row.get('title', '?')}》"
                )
                result["summaries_skipped"] += 1
                continue
            movie = session.scalar(
                select(Movie).where(Movie.douban_id == int(douban_id))
            )
            if movie is None:
                logger.warning(f"摘要找不到对应电影，跳过：douban_id={douban_id}")
                result["summaries_skipped"] += 1
                continue
            existing = session.scalar(
                select(AISummary).where(AISummary.movie_id == movie.movie_id)
            )
            if existing is not None:
                result["summaries_skipped"] += 1
                continue
            summary = AISummary(
                movie_id=movie.movie_id,
                summary=row["summary"],
                model_name=row["model_name"],
            )
            created_at = parse_created_at(row.get("created_at", ""))
            if created_at is not None:
                summary.created_at = created_at
            session.add(summary)
            result["summaries_inserted"] += 1

        session.commit()

    logger.info(
        "电影：新增 %d / 更新 %d；摘要：新增 %d / 跳过 %d；未调用 AI 接口",
        result["movies_inserted"], result["movies_updated"],
        result["summaries_inserted"], result["summaries_skipped"],
    )
    return result


def main() -> None:
    from logging_setup import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(
        description="把电影和 AI 摘要 CSV 导入网页数据库（DATABASE_URL）"
    )
    parser.add_argument("--confirm-import", action="store_true")
    args = parser.parse_args()
    if not args.confirm_import:
        raise SystemExit(
            "该操作会写入 DATABASE_URL 指向的数据库，请添加 --confirm-import。"
        )
    import_web_data()


if __name__ == "__main__":
    main()
