"""项目统一日志配置：控制台 + 滚动文件，默认 INFO 级别。

各入口脚本调用 configure_logging() 一次，业务模块只需
logging.getLogger(__name__)。Vercel 等无盘环境写文件失败时
自动退化为仅控制台输出。
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from paths import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
DEFAULT_LOG_FILE = LOG_DIR / "app.log"

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
    force: bool = False,
) -> None:
    root = logging.getLogger()
    if root.handlers and not force:
        return
    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    target = log_file or DEFAULT_LOG_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # 只读文件系统（如 Vercel）上退化为控制台日志，由平台收集
        root.warning("日志文件不可写，仅输出到控制台：%s", target)

    if os.getenv("LOG_LEVEL"):
        root.setLevel(os.environ["LOG_LEVEL"].upper())
