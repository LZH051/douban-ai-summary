import hashlib
import hmac
import re
import secrets


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_valid_email(value: str) -> bool:
    return len(value) <= 255 and bool(EMAIL_PATTERN.fullmatch(value))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (TypeError, ValueError):
        return False


def csrf_token(session: dict) -> str:
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf(session: dict, submitted: str) -> bool:
    expected = session.get("csrf_token", "")
    return bool(expected and submitted) and hmac.compare_digest(expected, submitted)


# 供"邮箱不存在"分支做等时校验：短路路径与 scrypt 路径响应时间
# 差两个数量级，足以枚举注册邮箱（时序侧信道）
DUMMY_PASSWORD_HASH = hash_password("timing-equalizer-not-a-real-password")
