# 豆瓣电影 Top250 数据分析与 AI 摘要工具（SQLite 版）

这是项目 B 的独立 SQLite 版本。数据库保存在
`database/douban_ai.db`，不需要安装或启动 MySQL/Wampserver。

## 功能

- 使用 `requests + BeautifulSoup` 低频采集电影信息
- 清洗非法字段、空简介和重复电影
- 使用 SQLite 唯一约束与 `INSERT OR IGNORE` 防止重复入库
- 可生成5～10条 AI 摘要
- 可将 MySQL 版本已生成的摘要 CSV 导入 SQLite，避免重复付费

## 安装

```powershell
cd E:\douban-ai-summary-sqlite
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

SQLite 驱动属于 Python 标准库，无需另外安装。

## 使用现有数据完成入库

```powershell
python src\cleaner.py
python src\load_database.py
python src\load_database.py
python src\import_ai_summaries.py
python src\verify_project.py --expected-min 20 --require-ai
```

`import_ai_summaries.py` 只导入现有 CSV，不会调用 API。

## 重新采集一页

```powershell
python src\main.py --pages 1
```

多页采集时每页随机等待2～5秒；遇到403、418或429会停止。

## 新增 AI 摘要

只有明确接受接口费用后才运行：

```powershell
python src\ai_summary.py --limit 5 --confirm-paid-run
```

数据库文件可用 DB Browser for SQLite 打开：

```text
E:\douban-ai-summary-sqlite\database\douban_ai.db
```

`.env`、`.db` 和虚拟环境均已加入 `.gitignore`。
