# 豆瓣电影 Top250 数据分析与 AI 摘要工具（SQLite 版）

本项目使用 `requests + BeautifulSoup` 低频采集豆瓣电影 Top250 数据，
经过清洗和去重后写入 SQLite，并为部分电影生成 AI 摘要。数据库位于
`database/douban_ai.db`，无需安装或启动数据库服务器。

## 功能

- 采集电影标题、评分、评价人数、简介和来源链接
- 多页采集时随机等待2～5秒
- 遇到403、418或429时停止，不进行高频重试
- 清洗缺失字段、非法数据和重复电影
- 使用 SQLite 保存电影和 AI 摘要
- 使用唯一约束和 `INSERT OR IGNORE` 防止重复入库
- 支持生成5～10条 AI 摘要
- 支持导入现有摘要 CSV，不重复调用付费接口

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
第二次运行 `load_database.py` 应显示新增0条、跳过25条。

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
