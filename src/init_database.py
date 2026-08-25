import logging
from db import connect_to_database, get_database_path
from paths import SCHEMA_FILE, ensure_directories

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    ensure_directories()
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection = connect_to_database()
    try:
        connection.executescript(schema)
        connection.commit()
    finally:
        connection.close()
    logger.info(f"SQLite 初始化成功：{get_database_path()}")


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    initialize_database()
