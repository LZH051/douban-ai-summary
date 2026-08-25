import logging
import csv
import json
import re
from decimal import Decimal, InvalidOperation

from paths import (
    CLEAN_DATA_FILE,
    CLEANING_REPORT_FILE,
    RAW_DATA_FILE,
    ensure_directories,
)

logger = logging.getLogger(__name__)


FIELDNAMES = [
    "douban_id",
    "title",
    "rating",
    "rating_count",
    "introduction",
    "introduction_source",
    "source_url",
    "collected_at",
]

INTRODUCTION_SOURCES = ("inq", "metadata", "placeholder")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def infer_introduction_source(introduction: str) -> str:
    """为没有 introduction_source 列的历史数据按内容推断来源。"""
    if not introduction or introduction == "暂无简介":
        return "placeholder"
    if introduction.startswith("导演") or "主演:" in introduction:
        return "metadata"
    return "inq"


def clean_data() -> list[dict[str, str]]:
    ensure_directories()
    if not RAW_DATA_FILE.exists():
        raise FileNotFoundError(f"未找到采集数据：{RAW_DATA_FILE}")

    with RAW_DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        raw_rows = list(csv.DictReader(file))

    cleaned_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    report = {
        "raw_count": len(raw_rows),
        "fixed_missing_introduction": 0,
        "removed_invalid": 0,
        "removed_duplicate": 0,
        "clean_count": 0,
        # 按来源分组统计简介质量：降级路径必须可见，不能混在"非空即正常"里
        "introduction_sources": {source: 0 for source in INTRODUCTION_SOURCES},
    }

    for raw_row in raw_rows:
        row = {
            field: normalize_text(raw_row.get(field) or "")
            for field in FIELDNAMES
        }

        if not row["introduction"]:
            row["introduction"] = "暂无简介"
            row["introduction_source"] = "placeholder"
            report["fixed_missing_introduction"] += 1
        if row["introduction_source"] not in INTRODUCTION_SOURCES:
            row["introduction_source"] = infer_introduction_source(
                row["introduction"]
            )

        try:
            rating = Decimal(row["rating"])
            rating_count = int(row["rating_count"])
            douban_id = int(row["douban_id"])
        except (InvalidOperation, ValueError):
            report["removed_invalid"] += 1
            continue

        if (
            not row["title"]
            or not row["source_url"]
            or not row["collected_at"]
            or not Decimal("0") <= rating <= Decimal("10")
            or rating_count < 0
            or douban_id <= 0
        ):
            report["removed_invalid"] += 1
            continue

        if row["douban_id"] in seen_ids:
            report["removed_duplicate"] += 1
            continue

        seen_ids.add(row["douban_id"])
        row["rating"] = format(rating, ".1f")
        row["rating_count"] = str(rating_count)
        report["introduction_sources"][row["introduction_source"]] += 1
        cleaned_rows.append(row)

    report["clean_count"] = len(cleaned_rows)

    with CLEAN_DATA_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    CLEANING_REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"清洗前：{report['raw_count']} 条")
    logger.info(f"补全简介：{report['fixed_missing_introduction']} 条")
    sources = report["introduction_sources"]
    logger.info(
        "简介来源分布：短评 {inq} 条 / 元信息降级 {metadata} 条 / "
        "占位 {placeholder} 条".format(**sources)
    )
    logger.info(f"删除非法数据：{report['removed_invalid']} 条")
    logger.info(f"删除重复数据：{report['removed_duplicate']} 条")
    logger.info(f"清洗后：{report['clean_count']} 条")
    return cleaned_rows


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    clean_data()

