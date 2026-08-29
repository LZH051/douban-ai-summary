# 光影智选｜豆瓣电影 Top250 AI 摘要与正版观看导航

光影智选是一个基于 FastAPI 的电影信息网站，提供豆瓣电影 Top250 浏览、评分筛选、AI 摘要、用户收藏和正版视频平台搜索入口。

## 在线体验

- 网站首页：<https://douban-ai-summary.vercel.app/>

## 当前数据

- 电影：250 部
- 已有 AI 摘要：5 条
- 列表分页：每页 12 部，共 21 页
- 数据库存储：本地使用 SQLite，公网使用 Neon PostgreSQL

AI 摘要保存在数据库中，普通用户浏览时不会重复调用 AI 接口。没有摘要的电影会显示“暂时还没有 AI 摘要”。

## 主要功能

### 公网网站

- 用户注册、登录和退出
- 按电影名称搜索
- 按最低评分筛选
- 电影列表分页与首尾页跳转
- 查看评分、评价人数、简介和资料来源
- 阅读已保存的 AI 摘要
- 收藏或取消收藏电影
- 跳转到爱奇艺、腾讯视频、优酷和哔哩哔哩搜索电影
- 管理员维护确定的正版播放页面链接
- 电影库页有当前筛选范围的评分分布直方图（本地自托管 Chart.js，无 CDN）
- 收藏页显示个人统计（收藏数、平均分、最高分）
- 手机（H5）与电脑浏览器均已适配：移动端抽屉导航、单列卡片、精简分页

### 语义找片（RAG 检索）

- `/search` 页面与 `GET /api/v1/search?q=`：用一句话描述找电影（如"讲越狱的高分片"）
- 语料 = 片名 + 豆瓣短评/简介 +（如有）AI 摘要，存入本地 Chroma 向量库
- 构建索引：`python src/build_index.py --confirm-paid-run`（需配置
  `AI_EMBEDDING_MODEL`；未配置时可用 `--offline-hash` 构建零费用的字面匹配索引做本地演示）
- 幂等与成本控制：按 douban_id upsert，内容未变的电影不重复向量化
- 索引未构建/配置缺失时页面与 API 都会明确降级提示

### AI 摘要：双引擎 + Prompt 评测

- 手写链路 `src/ai_summary.py` 与 LangChain 链路 `src/ai_summary_lc.py`
  并存，行为对齐、共享缓存；取舍分析见
  [`docs/langchain_notes.md`](docs/langchain_notes.md)
- Prompt 评测集 `evals/summary_cases.jsonl`（10 条真实电影）：
  `python evals/run_eval.py --use-cached` 免费回放历史输出判分；
  `python evals/run_eval.py --engine lc --confirm-paid-run --save-cache`
  在线实跑并更新缓存。规则：非空/≤80字/含片名/不复述评分与人数/
  无臆测词，报告输出到 `evals/report.json`

### JSON API（/api/v1）

错误统一封装为 `{"error": {"code", "message"}}`：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/movies` | 搜索/评分筛选/分页（`q`/`min_rating`/`page`/`page_size`≤100） |
| GET | `/api/v1/movies/{id}` | 详情，含 AI 摘要与正版链接 |
| GET | `/api/v1/search` | 语义检索（`q`/`top_k`≤20） |
| GET | `/api/v1/favorites` | 我的收藏（需登录会话） |
| POST | `/api/v1/movies/{id}/favorite` | 收藏切换（需登录会话） |

`/health` 会真实探测数据库，异常时返回 503。交互式文档见 `/docs`。

### 安全

- 登录失败限流（同一邮箱 15 分钟 5 次）；登录校验做了等时处理防邮箱枚举
- 响应头含 CSP、线上 HSTS；收藏页 Cache-Control: no-store
- 线上环境缺少 `SESSION_SECRET` 或 `DATABASE_URL` 会拒绝启动，不再静默降级

### 数据处理工具

- 使用 `requests + BeautifulSoup` 低频采集电影信息
- 清洗空字段、非法值和重复电影
- 使用 Upsert 更新已有电影，避免重复入库
- 支持命令行查询、统计和手动录入
- AI 摘要单次限制 1～10 条，并要求显式确认付费调用

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy
- 页面：Jinja2、HTML、CSS
- 本地数据库：SQLite
- 公网数据库：Neon PostgreSQL
- 部署：Vercel
- 数据采集：Requests、BeautifulSoup
- AI 接口：OpenAI 兼容接口／火山方舟

## 项目结构

```text
api/                 Vercel FastAPI 入口
src/                 后端、数据处理和导入脚本
static/              黄黑主题样式
templates/           页面模板
data/                原始和清洗后的电影 CSV
output/              AI 摘要、清洗报告和采集异常
database/            SQLite 建表脚本；本地 .db 不提交 GitHub
tests/               网页冒烟测试与单元测试
```

## 本地安装

Windows PowerShell：

```powershell
cd E:\douban-ai-summary-sqlite
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

不需要激活虚拟环境，可以直接使用 `.venv` 内的 Python，避免 PowerShell 执行策略拦截 `Activate.ps1`。

## 环境变量

编辑本地 `.env`：

```env
# AI 摘要功能，可选
AI_API_KEY=
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
AI_MODEL=doubao-seed-2-0-lite-260428

# 网页功能
DATABASE_URL=
SESSION_SECRET=
ADMIN_EMAILS=
```

说明：

- 本地不填写 `DATABASE_URL` 时，网页默认使用 `database/douban_ai.db`。
- 公网部署必须设置 `DATABASE_URL` 和 `SESSION_SECRET`。
- `ADMIN_EMAILS` 可选，用于指定能够维护正版链接的管理员邮箱。
- `.env`、数据库文件和密钥禁止提交到 GitHub。

## 本地运行网站

```powershell
.\.venv\Scripts\python.exe -m uvicorn web_app:app --app-dir src --reload
```

浏览器打开：<http://127.0.0.1:8000>

## 数据采集、清洗和入库

默认只低频采集一页：

```powershell
.\.venv\Scripts\python.exe src\main.py --pages 1
```

采集完整 Top250：

```powershell
.\.venv\Scripts\python.exe src\main.py --pages 10
```

保护措施：

- 页数限制为 1～10 页
- 每页随机等待 2～5 秒
- 请求超时为 20 秒
- 遇到 403、418 或 429 时立即停止，不连续重试
- 采集流程不会自动调用 AI

单独执行清洗、入库和验收：

```powershell
.\.venv\Scripts\python.exe src\cleaner.py
.\.venv\Scripts\python.exe src\load_database.py
.\.venv\Scripts\python.exe src\verify_project.py --expected-min 250 --require-ai
```

## AI 摘要

只有明确接受接口费用后才执行：

```powershell
.\.venv\Scripts\python.exe src\ai_summary.py --limit 5 --confirm-paid-run
```

程序只选择尚未生成摘要的电影。每部电影的摘要保存在数据库中，后续用户浏览不会重复收费。

## 导入 Neon PostgreSQL

在本地 `.env` 中配置 Neon 直连字符串后执行：

```powershell
.\.venv\Scripts\python.exe src\import_web_data.py --confirm-import
```

该脚本将 250 部电影和已有 AI 摘要导入网页数据库，支持重复运行，不会调用 AI。

## Vercel 部署

1. 将代码上传到 GitHub，但不要上传 `.env`、`.db`、虚拟环境或日志。
2. 在 Vercel 导入 GitHub 仓库，预设选择 FastAPI，根目录保持 `./`。
3. 在 Vercel 设置环境变量：

```text
DATABASE_URL=Neon 的 pooler 连接字符串
SESSION_SECRET=随机长字符串
ADMIN_EMAILS=管理员注册邮箱（可选）
```

4. 点击 Deploy，并访问 `/health`、`/movies` 和 `/register` 验证部署。

## 测试

安装开发依赖后，一条命令运行全部测试：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

临时数据库与登录态由 `tests/conftest.py` 提供，每个用例独享干净数据库。
推送到 GitHub 后，`.github/workflows/tests.yml` 会自动运行同样的测试。

## Vercel 部署

1. 将代码上传到 GitHub，但不要上传 `.env`、`.db`、虚拟环境或日志。
2. 在 Vercel 导入 GitHub 仓库，预设选择 FastAPI，根目录保持 `./`。
3. 在 Vercel 设置环境变量：

```text
DATABASE_URL=Neon 的 pooler 连接字符串
SESSION_SECRET=随机长字符串
ADMIN_EMAILS=管理员注册邮箱（可选）
```

4. 点击 Deploy，并访问 `/health`、`/movies` 和 `/register` 验证部署。

## 测试

```powershell
.\.venv\Scripts\python.exe tests\web_smoke_test.py
.\.venv\Scripts\python.exe tests\introduction_source_test.py
.\.venv\Scripts\python.exe tests\import_summaries_key_test.py
.\.venv\Scripts\python.exe tests\ai_robustness_test.py
.\.venv\Scripts\python.exe tests\import_web_data_test.py
.\.venv\Scripts\python.exe tests\logging_setup_test.py
.\.venv\Scripts\python.exe tests\web_p0_fixes_test.py
.\.venv\Scripts\python.exe tests\api_v1_test.py
.\.venv\Scripts\python.exe tests\security_hardening_test.py
```

预期输出：

```text
WEB_SMOKE_TEST=PASS
```

## 隐私与版权说明

- 网站不保存、上传或分发电影视频文件。
- 正版平台按钮用于跳转到第三方平台官网搜索，或者跳转到管理员录入的确定播放页。
- 搜索结果不代表相应平台一定拥有该电影版权，片源、会员和付费规则以平台官网为准。
- 用户密码采用带随机盐的 scrypt 哈希保存，不保存明文密码。
- 用户账户和收藏数据存储在数据库中，不应提交到公开代码仓库。

## 项目用途

本项目用于学习 Python 数据采集、ETL、SQLite/PostgreSQL、FastAPI、多用户网站开发和云端部署。
