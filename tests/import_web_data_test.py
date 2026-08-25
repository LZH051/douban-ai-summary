"""import_web_data 测试：README 承诺的网页数据库导入脚本必须真实存在。

要求：
1. 把清洗后的电影 CSV 和 AI 摘要 CSV 导入 Web 数据库（DATABASE_URL）；
2. 摘要按 douban_id 关联；
3. 可重复运行（upsert，不产生重复数据）。
"""

import csv
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

MOVIE_FIELDS = [
    "douban_id", "title", "rating", "rating_count",
    "introduction", "introduction_source", "source_url", "collected_at",
]
SUMMARY_FIELDS = ["douban_id", "title", "summary", "model_name", "created_at"]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'web.db'}"

        import import_web_data
        from sqlalchemy import select
        from web_database import SessionLocal
        from web_models import AISummary, Movie

        movies_csv = workdir / "movies.csv"
        summaries_csv = workdir / "summaries.csv"
        write_csv(movies_csv, MOVIE_FIELDS, [
            {
                "douban_id": "1292052", "title": "肖申克的救赎",
                "rating": "9.7", "rating_count": "3120000",
                "introduction": "希望让人自由。", "introduction_source": "inq",
                "source_url": "https://movie.douban.com/subject/1292052/",
                "collected_at": "2026-07-26 14:12:44",
            },
            {
                "douban_id": "1291546", "title": "霸王别姬",
                "rating": "9.6", "rating_count": "2100000",
                "introduction": "风华绝代。", "introduction_source": "inq",
                "source_url": "https://movie.douban.com/subject/1291546/",
                "collected_at": "2026-07-26 14:12:44",
            },
        ])
        write_csv(summaries_csv, SUMMARY_FIELDS, [{
            "douban_id": "1291546", "title": "霸王别姬",
            "summary": "程蝶衣的一生。", "model_name": "m",
            "created_at": "2026-07-27 01:18:04",
        }])
        import_web_data.CLEAN_DATA_FILE = movies_csv
        import_web_data.AI_SUMMARY_FILE = summaries_csv

        result = import_web_data.import_web_data()
        assert result["movies_inserted"] == 2, result
        assert result["summaries_inserted"] == 1, result

        # 重复运行必须幂等
        result = import_web_data.import_web_data()
        assert result["movies_inserted"] == 0, result
        assert result["movies_updated"] == 2, result
        assert result["summaries_inserted"] == 0, result

        with SessionLocal() as session:
            assert session.scalar(
                select(Movie).where(Movie.douban_id == 1292052)
            ).title == "肖申克的救赎"
            summaries = session.scalars(select(AISummary)).all()
            assert len(summaries) == 1, summaries
            assert summaries[0].movie.douban_id == 1291546

    print("IMPORT_WEB_DATA_TEST=PASS")


if __name__ == "__main__":
    main()
