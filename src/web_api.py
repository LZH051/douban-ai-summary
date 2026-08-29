"""JSON API v1。

- 电影检索/详情是公开接口；收藏接口沿用登录会话 Cookie。
- 错误统一封装 {"error": {"code", "message"}}，由 web_app 注册的
  异常处理器完成。
- 收藏切换只接受无表单体的 POST：SameSite=Lax 会话 Cookie 不随
  跨站请求发送，无需表单 CSRF token。
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from web_database import SessionLocal
from web_models import AISummary, Favorite, Movie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

DEFAULT_PAGE_SIZE = 12


def serialize_movie(movie: Movie, with_detail: bool = False) -> dict:
    data = {
        "movie_id": movie.movie_id,
        "douban_id": movie.douban_id,
        "title": movie.title,
        "rating": movie.rating,
        "rating_count": movie.rating_count,
        "ai_summary": movie.ai_summary.summary if movie.ai_summary else None,
    }
    if with_detail:
        data["introduction"] = movie.introduction
        data["source_url"] = movie.source_url
        data["watch_links"] = [
            {"platform_name": link.platform_name, "watch_url": link.watch_url}
            for link in movie.watch_links
        ]
    return data


def require_user(request: Request, database):
    from web_app import get_user

    user = get_user(request, database)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


@router.get("/movies")
def list_movies(
    q: str = "",
    min_rating: float = Query(0, ge=0, le=10),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
):
    q = q.strip()[:80]
    conditions = []
    if q:
        conditions.append(Movie.title.ilike(f"%{q}%"))
    if min_rating:
        conditions.append(Movie.rating >= min_rating)
    with SessionLocal() as database:
        total = database.scalar(
            select(func.count()).select_from(Movie).where(*conditions)
        ) or 0
        pages = max(1, -(-total // page_size))
        page = min(page, pages)
        movies = database.scalars(
            select(Movie)
            .options(selectinload(Movie.ai_summary))
            .where(*conditions)
            .order_by(Movie.rating.desc(), Movie.rating_count.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [serialize_movie(movie) for movie in movies],
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        }


@router.get("/movies/{movie_id}")
def movie_detail(movie_id: int):
    with SessionLocal() as database:
        movie = database.scalar(
            select(Movie)
            .options(selectinload(Movie.ai_summary), selectinload(Movie.watch_links))
            .where(Movie.movie_id == movie_id)
        )
        if movie is None:
            raise HTTPException(status_code=404, detail="电影不存在。")
        return serialize_movie(movie, with_detail=True)


@router.get("/favorites")
def list_favorites(request: Request):
    with SessionLocal() as database:
        user = require_user(request, database)
        movies = database.scalars(
            select(Movie)
            .join(Favorite)
            .options(selectinload(Movie.ai_summary))
            .where(Favorite.user_id == user.id)
            .order_by(Favorite.created_at.desc())
        ).all()
        return {
            "items": [serialize_movie(movie) for movie in movies],
            "total": len(movies),
        }


@router.post("/movies/{movie_id}/favorite")
def toggle_favorite(request: Request, movie_id: int):
    with SessionLocal() as database:
        user = require_user(request, database)
        if not database.get(Movie, movie_id):
            raise HTTPException(status_code=404, detail="电影不存在。")
        existing = database.scalar(
            select(Favorite).where(
                Favorite.user_id == user.id, Favorite.movie_id == movie_id
            )
        )
        if existing:
            database.delete(existing)
            database.commit()
            favorite = False
        else:
            database.add(Favorite(user_id=user.id, movie_id=movie_id))
            try:
                database.commit()
            except IntegrityError:
                database.rollback()
            favorite = True
        logger.info(
            "API 收藏切换 user=%s movie=%s favorite=%s",
            user.id, movie_id, favorite,
        )
        return {"movie_id": movie_id, "favorite": favorite}
