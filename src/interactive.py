from datetime import datetime
from decimal import Decimal, InvalidOperation

from ai_summary import generate_ai_summaries
from db import connect_to_database
from init_database import initialize_database


def read_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("该项不能为空，请重新输入。")


def read_positive_int(prompt: str, allow_zero: bool = False) -> int:
    while True:
        try:
            value = int(input(prompt).strip())
        except ValueError:
            print("请输入整数。")
            continue
        if value > 0 or (allow_zero and value == 0):
            return value
        print("请输入有效的非负整数。" if allow_zero else "请输入大于0的整数。")


def read_rating() -> float:
    while True:
        try:
            value = Decimal(input("评分（0～10）：").strip())
        except InvalidOperation:
            print("评分必须是数字。")
            continue
        if Decimal("0") <= value <= Decimal("10"):
            return float(value.quantize(Decimal("0.1")))
        print("评分必须在0～10之间。")


def add_or_update_movie() -> None:
    douban_id = read_positive_int("豆瓣 ID：")
    title = read_required("电影名称：")
    rating = read_rating()
    rating_count = read_positive_int("评价人数：", allow_zero=True)
    introduction = read_required("简介：")
    source_url = read_required("来源地址：")
    if not source_url.startswith(("http://", "https://")):
        print("来源地址必须以 http:// 或 https:// 开头。")
        return
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection = connect_to_database()
    try:
        existed = connection.execute(
            "SELECT 1 FROM movies WHERE douban_id = ?", (douban_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT INTO movies (
                douban_id, title, rating, rating_count,
                introduction, source_url, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(douban_id) DO UPDATE SET
                title = excluded.title,
                rating = excluded.rating,
                rating_count = excluded.rating_count,
                introduction = excluded.introduction,
                source_url = excluded.source_url,
                collected_at = excluded.collected_at
            """,
            (
                douban_id, title, rating, rating_count,
                introduction, source_url, collected_at,
            ),
        )
        connection.commit()
        print("电影更新成功。" if existed else "电影添加成功。")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def print_movies(rows) -> None:
    if not rows:
        print("没有找到电影。")
        return
    for row in rows:
        print(
            f"- ID {row['movie_id']}｜{row['title']}｜评分 {row['rating']:.1f}｜"
            f"{row['rating_count']} 人评价"
        )


def search_movies() -> None:
    keyword = read_required("标题关键词：")
    connection = connect_to_database()
    try:
        rows = connection.execute(
            """
            SELECT movie_id, title, rating, rating_count
            FROM movies WHERE title LIKE ?
            ORDER BY rating DESC, rating_count DESC
            """,
            (f"%{keyword}%",),
        ).fetchall()
    finally:
        connection.close()
    print_movies(rows)


def filter_by_rating() -> None:
    minimum = read_rating()
    connection = connect_to_database()
    try:
        rows = connection.execute(
            """
            SELECT movie_id, title, rating, rating_count
            FROM movies WHERE rating >= ?
            ORDER BY rating DESC, rating_count DESC
            """,
            (minimum,),
        ).fetchall()
    finally:
        connection.close()
    print_movies(rows)


def show_statistics() -> None:
    connection = connect_to_database()
    try:
        totals = connection.execute(
            """
            SELECT COUNT(*) AS movie_count,
                   ROUND(AVG(rating), 2) AS average_rating,
                   MAX(rating) AS highest_rating
            FROM movies
            """
        ).fetchone()
        most_rated = connection.execute(
            """
            SELECT title, rating_count FROM movies
            ORDER BY rating_count DESC LIMIT 1
            """
        ).fetchone()
        summary_count = connection.execute(
            "SELECT COUNT(*) FROM ai_summaries"
        ).fetchone()[0]
    finally:
        connection.close()

    print(f"电影总数：{totals['movie_count']}")
    if totals["movie_count"]:
        print(f"平均评分：{totals['average_rating']:.2f}")
        print(f"最高评分：{totals['highest_rating']:.1f}")
        print(f"评价人数最多：{most_rated['title']}（{most_rated['rating_count']}人）")
    print(f"已有 AI 摘要：{summary_count}")
    print(f"尚无 AI 摘要：{totals['movie_count'] - summary_count}")


def generate_selected_summary() -> None:
    movie_id = read_positive_int("数据库电影 ID：")
    connection = connect_to_database()
    try:
        movie = connection.execute(
            "SELECT title FROM movies WHERE movie_id = ?", (movie_id,)
        ).fetchone()
    finally:
        connection.close()
    if not movie:
        print("没有找到该电影。")
        return
    print(f"将为《{movie['title']}》调用1次AI接口，可能产生费用。")
    if input("输入 yes 确认：").strip().lower() != "yes":
        print("已取消AI调用。")
        return
    generate_ai_summaries(
        limit=1,
        confirm_paid_run=True,
        movie_ids=[movie_id],
    )


def show_summaries() -> None:
    connection = connect_to_database()
    try:
        rows = connection.execute(
            """
            SELECT m.title, s.summary, s.model_name
            FROM ai_summaries AS s
            JOIN movies AS m ON m.movie_id = s.movie_id
            ORDER BY s.summary_id
            """
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        print("当前没有AI摘要。")
        return
    for row in rows:
        print(f"\n《{row['title']}》\n{row['summary']}\n模型：{row['model_name']}")


def run_interactive() -> None:
    initialize_database()
    actions = {
        "1": add_or_update_movie,
        "2": search_movies,
        "3": filter_by_rating,
        "4": show_statistics,
        "5": generate_selected_summary,
        "6": show_summaries,
    }
    while True:
        print(
            "\n电影数据与 AI 摘要工具\n"
            "1. 手动添加或更新电影\n2. 按标题搜索\n3. 按最低评分筛选\n"
            "4. 查看统计\n5. 为指定电影生成AI摘要\n6. 查看已有摘要\n0. 退出"
        )
        choice = input("请选择操作：").strip()
        if choice == "0":
            print("已退出。")
            return
        action = actions.get(choice)
        if not action:
            print("无效选项，请重新选择。")
            continue
        try:
            action()
        except Exception as error:
            print(f"操作失败：{error}")
