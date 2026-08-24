import csv
import random
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from paths import RAW_DATA_FILE, SCRAPING_ERROR_FILE, ensure_directories


TOP250_URL = "https://movie.douban.com/top250"
FIELDNAMES = [
    "douban_id", "title", "rating", "rating_count",
    "introduction", "source_url", "collected_at",
]
ERROR_FIELDNAMES = ["page_start", "source_url", "reason", "collected_at"]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_page(
    html: str,
    page_start: int = 0,
    errors: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in soup.select("div.item"):
        link = item.select_one("div.hd a")
        source_url = link.get("href", "").strip() if link else ""
        title_node = item.select_one("div.hd span.title")
        rating_node = item.select_one("span.rating_num")
        intro_node = item.select_one("span.inq")
        metadata_node = item.select_one("div.bd > p")

        if not link or not title_node or not rating_node:
            if errors is not None:
                errors.append({
                    "page_start": str(page_start),
                    "source_url": source_url,
                    "reason": "缺少链接、标题或评分节点",
                    "collected_at": collected_at,
                })
            continue

        id_match = re.search(r"/subject/(\d+)/", source_url)
        count_match = re.search(r"(\d+)\s*人评价", item.get_text(" ", strip=True))
        if not id_match or not count_match:
            if errors is not None:
                errors.append({
                    "page_start": str(page_start),
                    "source_url": source_url,
                    "reason": "无法解析豆瓣 ID 或评价人数",
                    "collected_at": collected_at,
                })
            continue

        if intro_node:
            introduction = normalize_text(intro_node.get_text(" ", strip=True))
        elif metadata_node:
            introduction = normalize_text(metadata_node.get_text(" ", strip=True))
        else:
            introduction = "暂无简介"

        rows.append({
            "douban_id": id_match.group(1),
            "title": normalize_text(title_node.get_text()),
            "rating": normalize_text(rating_node.get_text()),
            "rating_count": count_match.group(1),
            "introduction": introduction,
            "source_url": source_url,
            "collected_at": collected_at,
        })
    return rows


def write_scraping_errors(errors: list[dict[str, str]]) -> None:
    with SCRAPING_ERROR_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=ERROR_FIELDNAMES)
        writer.writeheader()
        writer.writerows(errors)


def fetch_page(session: requests.Session, start: int) -> str:
    response = session.get(
        TOP250_URL,
        params={"start": start, "filter": ""},
        timeout=20,
    )
    if response.status_code in {403, 418, 429}:
        raise RuntimeError(
            f"豆瓣返回 {response.status_code}，采集已停止。"
            "请降低频率并稍后再试，不要连续重试。"
        )
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def scrape_top250(
    pages: int = 1,
    delay_min: float = 2.0,
    delay_max: float = 5.0,
) -> list[dict[str, str]]:
    if not 1 <= pages <= 10:
        raise ValueError("pages 必须在 1～10 之间")
    if delay_min < 2 or delay_max < delay_min:
        raise ValueError("请求间隔必须满足 2 <= delay_min <= delay_max")

    ensure_directories()
    session = requests.Session()
    session.headers.update(HEADERS)
    all_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for page_index in range(pages):
        if page_index:
            delay = random.uniform(delay_min, delay_max)
            print(f"等待 {delay:.1f} 秒后请求下一页……")
            time.sleep(delay)
        start = page_index * 25
        print(f"采集第 {page_index + 1}/{pages} 页：start={start}")
        html = fetch_page(session, start)
        page_rows = parse_page(html, page_start=start, errors=errors)
        if not page_rows:
            write_scraping_errors(errors)
            raise RuntimeError(
                "页面请求成功，但没有解析到电影数据，可能是页面结构已变化。"
            )
        print(f"本页解析到 {len(page_rows)} 条")
        all_rows.extend(page_rows)

    with RAW_DATA_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)
    write_scraping_errors(errors)
    print(f"原始数据已保存：{RAW_DATA_FILE}")
    print(f"解析异常已保存：{SCRAPING_ERROR_FILE}（{len(errors)} 条）")
    print(f"共采集 {len(all_rows)} 条电影数据")
    return all_rows


if __name__ == "__main__":
    scrape_top250()
