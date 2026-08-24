# SQLite 改造说明

- MySQL 服务器连接改为 Python 标准库 `sqlite3`。
- 数据库由服务器实例改为本地 `database/douban_ai.db` 文件。
- `INSERT IGNORE` 改为 `INSERT OR IGNORE`，参数占位符 `%s` 改为 `?`。
- `SHOW TABLES` 改为查询 `sqlite_master`。
- 连接启用 `PRAGMA foreign_keys = ON`。
- 已有5条摘要通过 `output/ai_summaries.csv` 导入，不重复调用付费接口。
- 所有直接 AI 入口都要求 `--confirm-paid-run`。
