"""P0-2 复现测试：简介降级必须显性计数，不允许"报告说 0 异常、实际 100% 降级"。

- scraper.parse_page 必须为每条记录标注 introduction_source：
  inq（豆瓣短评）/ metadata（导演演员元信息降级）/ placeholder（占位）；
- cleaner 清洗报告必须按来源分组统计，历史 CSV（无该列）按内容推断回填。
"""

import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cleaner
import scraper

SAMPLE_HTML = """
<div>
  <div class="item">
    <div class="hd"><a href="https://movie.douban.com/subject/1292052/">
      <span class="title">肖申克的救赎</span></a></div>
    <div class="bd"><p>导演: 弗兰克·德拉邦特 主演: 蒂姆·罗宾斯 1994 / 美国 / 犯罪 剧情</p>
      <span class="rating_num">9.7</span><span>3120000人评价</span>
      <span class="inq">希望让人自由。</span></div>
  </div>
  <div class="item">
    <div class="hd"><a href="https://movie.douban.com/subject/1291546/">
      <span class="title">霸王别姬</span></a></div>
    <div class="bd"><p>导演: 陈凯歌 主演: 张国荣 1993 / 中国大陆 / 剧情 爱情</p>
      <span class="rating_num">9.6</span><span>2100000人评价</span></div>
  </div>
</div>
"""


def test_parse_page_marks_source() -> None:
    rows = scraper.parse_page(SAMPLE_HTML)
    assert len(rows) == 2, rows
    by_title = {row["title"]: row for row in rows}
    assert by_title["肖申克的救赎"]["introduction_source"] == "inq", by_title
    assert by_title["肖申克的救赎"]["introduction"] == "希望让人自由。"
    assert by_title["霸王别姬"]["introduction_source"] == "metadata", by_title


def test_cleaner_reports_source_counts() -> None:
    legacy_fields = [
        "douban_id", "title", "rating", "rating_count",
        "introduction", "source_url", "collected_at",
    ]
    rows = [
        {
            "douban_id": "1292052", "title": "肖申克的救赎", "rating": "9.7",
            "rating_count": "3120000", "introduction": "希望让人自由。",
            "source_url": "https://movie.douban.com/subject/1292052/",
            "collected_at": "2026-07-26 14:12:44",
        },
        {
            "douban_id": "1291546", "title": "霸王别姬", "rating": "9.6",
            "rating_count": "2100000",
            "introduction": "导演: 陈凯歌 主演: 张国荣 1993 / 中国大陆 / 剧情",
            "source_url": "https://movie.douban.com/subject/1291546/",
            "collected_at": "2026-07-26 14:12:44",
        },
        {
            "douban_id": "1295644", "title": "这个杀手不太冷", "rating": "9.4",
            "rating_count": "2500000", "introduction": "",
            "source_url": "https://movie.douban.com/subject/1295644/",
            "collected_at": "2026-07-26 14:12:44",
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        raw_file = workdir / "raw.csv"
        with raw_file.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=legacy_fields)
            writer.writeheader()
            writer.writerows(rows)
        cleaner.RAW_DATA_FILE = raw_file
        cleaner.CLEAN_DATA_FILE = workdir / "cleaned.csv"
        cleaner.CLEANING_REPORT_FILE = workdir / "report.json"
        cleaned = cleaner.clean_data()

        report = json.loads(
            cleaner.CLEANING_REPORT_FILE.read_text(encoding="utf-8")
        )
        sources = report["introduction_sources"]
        assert sources == {"inq": 1, "metadata": 1, "placeholder": 1}, report
        by_title = {row["title"]: row for row in cleaned}
        assert by_title["肖申克的救赎"]["introduction_source"] == "inq"
        assert by_title["霸王别姬"]["introduction_source"] == "metadata"
        assert by_title["这个杀手不太冷"]["introduction_source"] == "placeholder"


def main() -> None:
    test_parse_page_marks_source()
    test_cleaner_reports_source_counts()
    print("INTRODUCTION_SOURCE_TEST=PASS")


if __name__ == "__main__":
    main()
