import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from logging_setup import configure_logging
from web_database import Base, SessionLocal, engine
from web_models import Favorite, Movie, WatchLink, WebUser
from web_security import (
    csrf_token,
    hash_password,
    is_valid_email,
    normalize_email,
    valid_csrf,
    verify_password,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
PLATFORMS = ("爱奇艺", "腾讯视频", "优酷", "哔哩哔哩", "芒果TV", "其他正版平台")
MOVIES_PER_PAGE = 12

if os.getenv("VERCEL") and not SESSION_SECRET:
    raise RuntimeError("线上部署必须配置 SESSION_SECRET 环境变量。")
if not SESSION_SECRET:
    SESSION_SECRET = "local-development-only-change-before-deployment"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(2064082402)"))
            Base.metadata.create_all(bind=connection)
    else:
        Base.metadata.create_all(bind=engine)
    yield


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="光影智选", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=bool(os.getenv("VERCEL")),
    max_age=60 * 60 * 24 * 14,
)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("%s %s 未捕获异常", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s %s %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def flash(request: Request, message: str, kind: str = "success") -> None:
    request.session["messages"] = [{"text": message, "kind": kind}]


def get_user(request: Request, database: Session) -> WebUser | None:
    user_id = request.session.get("user_id")
    return database.get(WebUser, user_id) if isinstance(user_id, int) else None


def is_admin(user: WebUser | None) -> bool:
    allowed = {
        normalize_email(item)
        for item in os.getenv("ADMIN_EMAILS", "").split(",")
        if item.strip()
    }
    return bool(user and user.email in allowed)


def render(request: Request, name: str, *, user=None, status_code=200, **values):
    context = {
        "request": request,
        "current_user": user,
        "is_admin": is_admin(user),
        "csrf_token": csrf_token(request.session),
        "messages": request.session.pop("messages", []),
        **values,
    }
    return templates.TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )


def require_csrf(request: Request, submitted: str) -> None:
    if not valid_csrf(request.session, submitted):
        raise HTTPException(status_code=400, detail="请求已失效，请刷新页面后重试。")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as database:
        user = get_user(request, database)
        movies = database.scalars(
            select(Movie)
            .options(selectinload(Movie.ai_summary))
            .order_by(Movie.rating.desc(), Movie.rating_count.desc())
            .limit(6)
        ).all()
        return render(request, "home.html", user=user, movies=movies)


@app.get("/movies", response_class=HTMLResponse)
def movie_list(request: Request, q: str = "", min_rating: float = 0, page: int = 1):
    q = q.strip()[:80]
    min_rating = max(0, min(10, min_rating))
    page = max(1, page)
    with SessionLocal() as database:
        user = get_user(request, database)
        conditions = []
        if q:
            conditions.append(Movie.title.ilike(f"%{q}%"))
        if min_rating:
            conditions.append(Movie.rating >= min_rating)

        total = database.scalar(
            select(func.count()).select_from(Movie).where(*conditions)
        ) or 0
        total_pages = max(1, (total + MOVIES_PER_PAGE - 1) // MOVIES_PER_PAGE)
        page = min(page, total_pages)
        query = select(Movie).options(selectinload(Movie.ai_summary)).where(*conditions)
        movies = database.scalars(
            query.order_by(Movie.rating.desc(), Movie.rating_count.desc())
            .offset((page - 1) * MOVIES_PER_PAGE)
            .limit(MOVIES_PER_PAGE)
        ).all()
        first_page_number = max(1, page - 2)
        last_page_number = min(total_pages, page + 2)
        return render(
            request, "movies.html", user=user, movies=movies,
            q=q, min_rating=min_rating, page=page, total=total,
            total_pages=total_pages,
            page_numbers=range(first_page_number, last_page_number + 1),
        )


@app.get("/movies/{movie_id}", response_class=HTMLResponse)
def movie_detail(request: Request, movie_id: int):
    with SessionLocal() as database:
        user = get_user(request, database)
        movie = database.scalar(
            select(Movie)
            .options(selectinload(Movie.ai_summary), selectinload(Movie.watch_links))
            .where(Movie.movie_id == movie_id)
        )
        if not movie:
            return render(request, "404.html", user=user, status_code=404)
        favorite = False
        if user:
            favorite = database.scalar(
                select(Favorite.id).where(
                    Favorite.user_id == user.id, Favorite.movie_id == movie_id
                )
            ) is not None
        return render(
            request, "movie_detail.html", user=user, movie=movie,
            favorite=favorite, platforms=PLATFORMS,
        )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return render(request, "register.html")


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf: str = Form(...),
):
    require_csrf(request, csrf)
    username, email = username.strip(), normalize_email(email)
    errors = []
    if not 2 <= len(username) <= 50:
        errors.append("用户名长度应为2至50个字符。")
    if not is_valid_email(email):
        errors.append("请输入有效邮箱地址。")
    if not 8 <= len(password) <= 128:
        errors.append("密码长度应为8至128个字符。")
    if password != password_confirm:
        errors.append("两次输入的密码不一致。")
    if errors:
        return render(
            request, "register.html", errors=errors,
            form={"username": username, "email": email}, status_code=422,
        )
    with SessionLocal() as database:
        user = WebUser(username=username, email=email, password_hash=hash_password(password))
        database.add(user)
        try:
            database.commit()
            database.refresh(user)
        except IntegrityError:
            database.rollback()
            return render(
                request, "register.html", errors=["该邮箱已经注册。"],
                form={"username": username, "email": email}, status_code=409,
            )
        request.session["user_id"] = user.id
    flash(request, "注册成功，欢迎来到光影智选。")
    return redirect("/movies")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(...),
):
    require_csrf(request, csrf)
    with SessionLocal() as database:
        user = database.scalar(
            select(WebUser).where(WebUser.email == normalize_email(email))
        )
        if not user or not verify_password(password, user.password_hash):
            return render(
                request, "login.html", error="邮箱或密码不正确。", status_code=401
            )
        request.session.clear()
        request.session["user_id"] = user.id
    return redirect("/movies")


@app.post("/logout")
def logout(request: Request, csrf: str = Form(...)):
    require_csrf(request, csrf)
    request.session.clear()
    return redirect("/")


@app.get("/favorites", response_class=HTMLResponse)
def favorites(request: Request):
    with SessionLocal() as database:
        user = get_user(request, database)
        if not user:
            return redirect("/login")
        movies = database.scalars(
            select(Movie)
            .join(Favorite)
            .where(Favorite.user_id == user.id)
            .order_by(Favorite.created_at.desc())
        ).all()
        return render(request, "favorites.html", user=user, movies=movies)


@app.post("/movies/{movie_id}/favorite")
def toggle_favorite(request: Request, movie_id: int, csrf: str = Form(...)):
    require_csrf(request, csrf)
    with SessionLocal() as database:
        user = get_user(request, database)
        if not user:
            return redirect("/login")
        if not database.get(Movie, movie_id):
            raise HTTPException(status_code=404)
        existing = database.scalar(
            select(Favorite).where(
                Favorite.user_id == user.id, Favorite.movie_id == movie_id
            )
        )
        if existing:
            database.delete(existing)
            message = "已取消收藏。"
        else:
            database.add(Favorite(user_id=user.id, movie_id=movie_id))
            message = "已加入我的收藏。"
        database.commit()
    flash(request, message)
    return redirect(f"/movies/{movie_id}")


@app.post("/movies/{movie_id}/watch-links")
def save_watch_link(
    request: Request,
    movie_id: int,
    platform_name: str = Form(...),
    watch_url: str = Form(...),
    csrf: str = Form(...),
):
    require_csrf(request, csrf)
    with SessionLocal() as database:
        user = get_user(request, database)
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="仅管理员可以维护正版链接。")
        if platform_name not in PLATFORMS:
            raise HTTPException(status_code=422, detail="请选择有效平台。")
        watch_url = watch_url.strip()
        if not watch_url.startswith("https://") or len(watch_url) > 1000:
            raise HTTPException(status_code=422, detail="请输入有效的 HTTPS 正版链接。")
        existing = database.scalar(
            select(WatchLink).where(
                WatchLink.movie_id == movie_id,
                WatchLink.platform_name == platform_name,
            )
        )
        if existing:
            existing.watch_url = watch_url
        else:
            database.add(
                WatchLink(movie_id=movie_id, platform_name=platform_name, watch_url=watch_url)
            )
        database.commit()
    flash(request, "正版观看链接已保存。")
    return redirect(f"/movies/{movie_id}")


@app.post("/watch-links/{link_id}/delete")
def delete_watch_link(request: Request, link_id: int, csrf: str = Form(...)):
    require_csrf(request, csrf)
    with SessionLocal() as database:
        user = get_user(request, database)
        if not is_admin(user):
            raise HTTPException(status_code=403)
        link = database.get(WatchLink, link_id)
        if not link:
            raise HTTPException(status_code=404)
        movie_id = link.movie_id
        database.delete(link)
        database.commit()
    return redirect(f"/movies/{movie_id}")


@app.exception_handler(404)
def not_found(request: Request, _exc):
    with SessionLocal() as database:
        return render(request, "404.html", user=get_user(request, database), status_code=404)
