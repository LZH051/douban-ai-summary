import os
import sqlite3
from pathlib import Path

from paths import DATABASE_FILE, PROJECT_ROOT


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_database_path() -> Path:
    load_dotenv_if_available()
    configured = os.getenv("SQLITE_DB_PATH", "").strip()
    path = Path(configured) if configured else DATABASE_FILE
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def connect_to_database() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
