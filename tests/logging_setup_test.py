"""日志基础设施测试：configure_logging 必须分级输出并落文件。"""

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import logging_setup


def test_logging_setup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "app.log"
        logging_setup.configure_logging(log_file=log_file, force=True)

        logger = logging.getLogger("test.module")
        logger.debug("debug 信息不应落盘")
        logger.info("信息级别日志")
        logger.warning("警告级别日志")

        content = log_file.read_text(encoding="utf-8")
        assert "信息级别日志" in content, content
        assert "警告级别日志" in content, content
        assert "debug 信息不应落盘" not in content, content
        assert "INFO" in content and "WARNING" in content, content
        assert "test.module" in content, content

        # 重复调用不得叠加 handler（否则日志会翻倍）
        logging_setup.configure_logging(log_file=log_file)
        logger.info("只出现一次")
        lines = [
            line
            for line in log_file.read_text(encoding="utf-8").splitlines()
            if "只出现一次" in line
        ]
        assert len(lines) == 1, lines

    print("LOGGING_SETUP_TEST=PASS")


if __name__ == "__main__":
    test_logging_setup()
