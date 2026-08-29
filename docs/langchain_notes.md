# 手写链路 vs LangChain：对比与取舍

两个实现并存，行为对齐（同一 prompt、30s 超时、最多 3 次重试、
单条失败跳过续跑、按 douban_id 缓存不重复计费）：

- 手写版：`src/ai_summary.py`（openai SDK + 自写 `call_with_retry`）
- LangChain 版：`src/ai_summary_lc.py`（`ChatPromptTemplate | ChatOpenAI.with_retry | StrOutputParser`）

## 逐项对比

| 维度 | 手写版 | LangChain 版 |
|---|---|---|
| 核心调用代码量 | ~60 行（含重试实现） | ~20 行（重试是一行 `.with_retry()`） |
| 新增依赖 | openai（本来就有） | langchain-core + langchain-openai（及其传递依赖，约 20+ 包） |
| Prompt 管理 | f-string 硬编码在函数里 | `ChatPromptTemplate` 模板对象，可单独测试、替换、版本化 |
| 重试语义可见性 | 完全透明：哪些异常重试、退避多久，代码里一行行写着 | 封装在 `.with_retry()` 里，出问题要读 LangChain 源码 |
| 可组合性 | 无。想加"输出解析→校验→兜底"要自己串 | 管道天然可扩展：`prompt \| llm \| parser \| validator` |
| 排错体验 | 栈短，指到自己的代码 | 栈深（Runnable 层层包装），新手排错更费劲 |
| 供应商切换 | 改 base_url 即可（OpenAI 兼容协议） | 换 `ChatOpenAI` 为其他集成类即可，接口不变 |

## 什么时候选哪个（面试答法）

- **单一模型、单轮调用、逻辑简单**（本项目现状）：手写版更合适——
  依赖少、行为透明、排错快。LangChain 在这种场景是过度设计。
- **链路开始复杂**（多步编排、RAG 检索拼接、工具调用、多模型
  切换、需要统一的流式/回调/追踪）：LangChain 的抽象开始回本，
  自己手写等于重新发明一个更差的框架。
- 团队协作维度：LangChain 的模板与管道是行业通用词汇，新人接手
  成本低；手写实现的质量取决于作者水平。

一句话：**先手写到疼，再上框架**——知道框架替你做了什么，
才配得上用它。

## 评测保障

`evals/run_eval.py` 对两个引擎输出同一套规则判分（非空/≤80字/
含片名/不复述评分与人数/无臆测词），切换实现前后跑一遍评测集，
通过率不得下降——这是"改 prompt 或换框架不悄悄劣化输出"的
回归门槛。
