# DataInsight Agent

English | 中文

## Overview
DataInsight Agent is an enterprise-grade, natural-language-driven data agent. It turns business questions into precise SQL via a Text-to-IR-to-SQL pipeline, grounded on a hybrid knowledge base: a Milvus vector store for semantic retrieval and a lightweight SQLite-based graph for structured knowledge. Orchestration is built with LlamaIndex (QueryPipeline + FnComponent). The agent includes an explicit IR (intermediate representation) layer and removes direct LLM SQL fallback for safety and transparency.

## Features
- Text-to-IR-to-SQL pipeline with safety-first generation (no direct LLM SQL fallback)
- Hybrid Knowledge Base: Milvus vectors + SQLite graph
- LlamaIndex-based orchestration with extensible components
- Structured logging with file and console outputs
- RAGFlow-style offline ETL wrapper for metadata ingestion
- Typer CLI for running agent, ETL, health checks, query rewrite inspection, and synthetic seeding

## Tech Stack
- Orchestration: LlamaIndex (default)
- Knowledge: Milvus (HNSW) + SQLite (local graph)
- Models: Pydantic v2 with type hints
- Logging: structlog + stdlib logging
- CLI: Typer

## Quick Start
1) Create and fill your `.env` (see variables below):
```bash
copy .env.example .env
```

2) Install dependencies (recommended: use a virtual environment):
```bash
pip install -r requirements.txt
```

3) Run health checks:
```bash
python -m datainsight_agent.cli check
```

4) Start the agent (demo):
```bash
# LlamaIndex engine
python -m datainsight_agent.cli run --question "What is monthly active users?"
```

### LlamaIndex Engine
- 默认启用；可通过 `ORCHESTRATOR_ENGINE=llamaindex` 明确指定。
- 组件化骨架：
  - deconstruct（含 Q2Q Tool-Call）
  - retrieve（两阶段 + RRF 融合，调用 `RetrievalService`）
  - plan → build_ir → execute（IR→SQL→校验/执行）
- 当前实现：优先使用 LlamaIndex `QueryPipeline` 以 `FnComponent` 串联上述组件；若不可用则自动回退到顺序执行。
- 与既有行为保持一致（澄清与默认时间窗口策略、timings 打点）。

5) Run ETL (dry-run by default). Use `--yes` to execute writes:
```bash
python -m datainsight_agent.cli etl --source ./metadata --dry-run
# Actually write to KB stores (requires confirmation flag)
python -m datainsight_agent.cli etl --source ./metadata --yes
```

## Configuration
Environment variables are loaded via `python-dotenv`. For the complete list and detailed explanations, see `ENVIRONMENT_VARIABLES_GUIDE.md`.

## Project Structure
```text
.
├─ .env.example
├─ CHANGELOG.md
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ logs/
└─ datainsight_agent/
   ├─ __init__.py
   ├─ __main__.py
   ├─ cli.py
   ├─ config/
   │  └─ settings.py
   ├─ common/
   │  └─ logging.py
   ├─ models/
   │  ├─ kb.py
   │  └─ ir.py
   ├─ clients/
   │  ├─ graph_client.py
   │  └─ vector_store.py
   ├─ services/
   │  ├─ retrieval.py
   │  ├─ sql_generator.py
   │  ├─ sql_executor.py
   │  └─ llm.py
   ├─ orchestrator/
   │  └─ li/
   │     ├─ __init__.py
   │     └─ pipeline.py
   └─ etl/
      └─ ragflow_etl.py
```

### Decoupled Architecture (目标解耦结构与用法)
```text
datainsight_agent/
├─ core/                        # 核心接口与类型（稳定契约）
│  ├─ interfaces.py             # Service 接口：QueryRewriter/TimeParser/…
│  ├─ types.py                  # 通用类型：TimeFilter/QueryRewrite/…
│  └─ exceptions.py             # 统一异常层次
├─ components/                  # 组件层（桥接到现有 services，便于接入）
│  ├─ query_rewriter/           # 查询重写组件（封装 Q2Q）
│  └─ time_parser/              # 时间解析组件（复用标准化逻辑）
├─ adapters/                    # 适配器层（DB/LLM/向量存储，可插拔）
├─ config/
│  ├─ settings.py               # 现有设置
│  └─ manager.py                # 统一配置门面（向上提供稳定配置对象）
├─ container/
│  └─ service_container.py      # 轻量依赖注入容器（注册/解析服务）
└─ services/                    # 现有实现（逐步迁移至组件）
```

示例：以解耦接口方式调用查询重写与时间解析
```python
from datainsight_agent.components.query_rewriter import QueryRewriter
from datainsight_agent.components.time_parser import TimeParser

rewriter = QueryRewriter()
res = rewriter.rewrite("查询2025年8月的MAU")
print(res.metric, res.time_filter)

parser = TimeParser()
tf = parser.parse("查询2025年8月的MAU")
print(tf)
```

说明：
- 组件通过 `core/` 定义的接口与类型对外暴露，内部复用现有 `services/` 逻辑，保证行为不变，同时便于主项目按接口集成。
- 配置读取统一由 `config/manager.py` 提供门面对象，遵循环境变量与 `.env.example` 约束。
- 后续阶段会将 SQL 生成/执行、指标解析、向量检索等逐步抽出为独立组件与适配器。

#### 组件直连示例：IRBuilder + SQL 生成与执行
```python
from datainsight_agent.components.query_rewriter import QueryRewriter
from datainsight_agent.components.ir_builder import IRBuilder
from datainsight_agent.components.sql_generator import SQLGeneratorComponent, SQLExecutorComponent

question = "查询2025年8月的MAU"

# 1) 重写：统一指标名/分组/时间
rew = QueryRewriter().rewrite(question)

# 2) 构建 IR：将 time_period → month，time_filter → WHERE（single/range/list）
ir = IRBuilder().build(rew)

# 3) 生成并执行 SQL
sql_text = SQLGeneratorComponent().generate(ir, "dws_user_activity_monthly")
rows = SQLExecutorComponent().execute(sql_text)
print(sql_text, rows)
```

> 注：`services/*` 现已标注为 legacy，被 `components/*` 桥接。新代码建议面向组件接口编程，可逐步替代旧路径。

## Safety & Compliance
- Sensitive credentials are managed strictly via environment variables. No hard-coded secrets.
- Destructive operations (e.g., ETL writes) require explicit confirmation (`--yes`).
- Structured logs are written to `logs/` with timestamps and levels.

## Roadmap
- Enrich IR and SQL generation with robust validation
- Optional pluggable backends for remote graph/vector stores
- Expand LLM tool choices and provider abstractions

---


## 环境与运行（推荐 uv）
优先使用 `uv` 来管理 Python 环境与运行（也可使用 `pip`，见上文）。
```bash
# 创建虚拟环境并安装依赖
uv venv
uv pip install -r requirements.txt


## CLI 子命令（统一清单）
- `check`：环境检查
- `db-init`：初始化最小 SQLite（演示）
- `db-init-dw-lite`：创建/扩展 DW-lite 表并写入示例数据
- `db-init-mysql`：初始化 MySQL 表并写入示例数据（需 `--yes` 与 `DATABASE_URL`）
- `run`：运行完整 Agent（Text→IR→SQL），可选 `--validate/--live/--execute`
- `etl`：离线 ETL（RAG 元数据），`--dry-run` 默认预览，`--yes` 执行
- `rewrite`：仅做 LLM 重写与 KB 上下文预览，不执行下游
- `ir-run`：手动构造 IR 并生成 SQL（验证 SQL 生成链路）
- `sql-preview`：受限 LLM 提示生成单条 SQL 并在 SQLite 预览
- `metrics-index`：构建/重建度量向量索引（HNSW）。示例：
  ```bash
  python -m datainsight_agent.cli metrics-index --rebuild --show-stats
  ```
- `db-seed-synthetic`：生成合成数据（LLM 或本地回退），支持 `--output` 写 NDJSON
- `log-test`：通过 structlog 管道写入一条测试日志
- `log-test-raw`：直接用 stdlib `RotatingFileHandler` 写日志（旁路）
- `timings`：顺序执行各节点并打印每个节点的耗时
 - 优化开关（可选）：
   - `DECONSTRUCT_SKIP_CONCEPTS_WHEN_Q2Q=1`：Q2Q 返回概念时跳过独立概念抽取（单轮 LLM）。
   - `DECONSTRUCT_SKIP_LLM_ON_CONFIDENT=1` + `RETRIEVE_CONFIDENCE_GATE`：向量高置信命中时跳过 LLM。
   - `TIME_REQUIRE_EXPLICIT=1`：未提供明确时间窗口时，优先澄清，而非默认套窗。

## 日志
- 目录：`LOG_DIR`（默认 `logs/`）；级别：`LOG_LEVEL`
- 运行中还会追加简单的调用记录到 `logs/agent_calls.log`
- 快速自检：
```bash
python -m datainsight_agent.cli log-test --message "hello"
python -m datainsight_agent.cli log-test-raw --path ./logs/datainsight_manual.log --message "hello"
```

## Q2Q（Query-to-Query 重写）配置
- `LLM_Q2Q_ENABLED`：是否启用 LLM+RAG 的重写（默认 1）
- `LLM_Q2Q_TOP_K`：重写阶段纳入的 KB 条目 Top-K（默认 6）
- 说明：当开启时，`deconstruct` 节点会并行触发 Q2Q 重写与概念抽取，以提升可扩展性与吞吐性能。
