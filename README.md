# 豆瓣电影 Top250 数据分析与 AI 摘要工具（SQLite 版）

这是项目 B 的独立 SQLite 版本。数据库保存在
`database/douban_ai.db`，不需要安装或启动 MySQL/Wampserver。

## 功能

- 使用 `requests + BeautifulSoup` 低频采集电影信息
- 清洗非法字段、空简介和重复电影
- 解析异常写入 `output/scraping_errors.csv`
- 使用 Upsert 新增电影并更新已有电影的最新数据
- 支持手动录入、标题搜索、评分筛选和数据统计
- 可选择指定电影生成AI摘要；单次限制1～10条
- AI调用必须明确确认，客户端关闭自动重试并设置30秒超时
- 可将已有摘要CSV导入SQLite，避免重复付费

## 安装

```powershell
cd E:\douban-ai-summary-sqlite
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

SQLite驱动属于Python标准库，无需另外安装。

## 数据清洗、入库与验收

使用已经采集的数据进行离线演示：

```powershell
python src\cleaner.py
python src\load_database.py
python src\load_database.py
python src\verify_project.py --expected-min 20 --require-ai
```

第二次运行 `load_database.py` 应显示新增0条、更新已有电影，证明
Upsert不会创建重复记录。`--require-ai` 只检查已有摘要，不调用API。

## 交互模式

```powershell
python src\main.py --interactive
```

可执行：

1. 手动添加或更新电影
2. 按标题关键词搜索
3. 按最低评分筛选
4. 查看电影总数、平均分、最高分和摘要数量
5. 选择指定电影生成AI摘要
6. 查看已有AI摘要

只有第5项在输入 `yes` 后才可能调用AI接口，其他操作均为本地SQLite操作。

## 重新低频采集

```powershell
python src\main.py --pages 1
```

多页采集时每页随机等待2～5秒；遇到403、418或429立即停止，不连续重试。
无法解析的电影节点会记录到：

```text
E:\douban-ai-summary-sqlite\output\scraping_errors.csv
```

## 批量新增AI摘要

只有明确接受接口费用后才运行：

```powershell
python src\ai_summary.py --limit 5 --confirm-paid-run
```

数据库文件可用DB Browser for SQLite打开：

```text
E:\douban-ai-summary-sqlite\database\douban_ai.db
```

`.env`、`.db` 和虚拟环境均已加入 `.gitignore`。
## 网页版本

网页提供电影搜索、评分筛选、AI摘要、用户收藏与正版观看入口。
正版观看按钮只跳转到管理员录入的第三方正版播放页，网站不存储视频。

```powershell
python -m pip install -r requirements.txt
python -m uvicorn web_app:app --app-dir src --reload
```

浏览器打开：`http://127.0.0.1:8000`。

本地默认继续使用 `database/douban_ai.db`。部署时设置 `DATABASE_URL`
可切换到 PostgreSQL，并且必须设置随机的 `SESSION_SECRET`。需要维护正版
观看链接时，将管理员邮箱写入 `ADMIN_EMAILS`；多个邮箱使用英文逗号分隔。
