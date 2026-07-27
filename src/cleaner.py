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


FIELDNAMES = [
    "douban_id",
    "title",
    "rating",
    "rating_count",
    "introduction",
    "source_url",
    "collected_at",
]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
    }

    for raw_row in raw_rows:
        row = {
            field: normalize_text(raw_row.get(field) or "")
            for field in FIELDNAMES
        }

        if not row["introduction"]:
            row["introduction"] = "暂无简介"
            report["fixed_missing_introduction"] += 1

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

    print(f"清洗前：{report['raw_count']} 条")
    print(f"补全简介：{report['fixed_missing_introduction']} 条")
    print(f"删除非法数据：{report['removed_invalid']} 条")
    print(f"删除重复数据：{report['removed_duplicate']} 条")
    print(f"清洗后：{report['clean_count']} 条")
    return cleaned_rows


if __name__ == "__main__":
    clean_data()

