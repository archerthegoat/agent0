# DataInsight Agent

English | 中文

## Overview
DataInsight Agent is an enterprise-grade, natural-language-driven data agent. It turns business questions into precise SQL via a Text-to-IR-to-SQL pipeline, grounded on a hybrid knowledge base: a local HNSW vector store for semantic retrieval and a lightweight SQLite-based graph for structured knowledge. Orchestration is built with LlamaIndex (QueryPipeline + FnComponent). The agent includes an explicit IR (intermediate representation) layer and removes direct LLM SQL fallback for safety and transparency.

## Features
- Text-to-IR-to-SQL pipeline with safety-first generation (no direct LLM SQL fallback)
- Hybrid Knowledge Base: Local HNSW vectors + SQLite graph
- LlamaIndex-based orchestration with extensible components
- Structured logging with file and console outputs
- RAGFlow-style offline ETL wrapper for metadata ingestion
- Typer CLI for running agent, ETL, health checks, query rewrite inspection, and synthetic seeding

## Tech Stack
- Orchestration: LlamaIndex (default)
- Knowledge: HNSW (hnswlib) + SQLite (local graph)
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

## Safety & Compliance
- Sensitive credentials are managed strictly via environment variables. No hard-coded secrets.
- Destructive operations (e.g., ETL writes) require explicit confirmation (`--yes`).
- Structured logs are written to `logs/` with timestamps and levels.

## Roadmap
- Enrich IR and SQL generation with robust validation
- Optional pluggable backends for remote graph/vector stores
- Expand LLM tool choices and provider abstractions

---

## 项目简介
DataInsight Agent 是一个企业级的智能数据代理，支持自然语言到 SQL 的安全转换。系统采用 Text-to-IR-to-SQL 流程，并使用本地混合知识库：HNSW（语义向量）+ SQLite（结构化知识）；编排由 LlamaIndex 驱动（QueryPipeline + 组件化）。

## 功能特性
- 文本→IR→SQL 的安全生成流程
- 本地混合知识库：HNSW（向量检索）+ SQLite（结构化元数据）
- 基于 LlamaIndex 的可扩展编排
- 结构化日志（控制台 + 文件）
- RAGFlow 风格的离线 ETL 封装
- Typer CLI（运行、ETL、健康检查）

## 快速开始
1）复制环境变量模板并填充：
```bash
copy .env.example .env
```

2）安装依赖（建议虚拟环境）：
```bash
pip install -r requirements.txt
```

3）运行健康检查：
```bash
python -m datainsight_agent.cli check
```

4）启动 Agent（示例）：
```bash
python -m datainsight_agent.cli run --question "本月 MAU 是多少？"
```

5）执行 ETL（默认 dry-run，写入需确认）：
```bash
python -m datainsight_agent.cli etl --source ./metadata --dry-run
python -m datainsight_agent.cli etl --source ./metadata --yes
```

## 配置说明
- 向量：`VECTOR_INDEX_DIR`，`VECTOR_SPACE`（ip|l2），`VECTOR_DIM`
- 本地图：`GRAPH_BACKEND=local`，`LOCAL_GRAPH_PATH`
- 日志：`LOG_LEVEL`，`LOG_DIR`
- LLM：`OPENAI_API_KEY`
- Q2Q：`LLM_Q2Q_ENABLED`（1/0 开关），`LLM_Q2Q_TOP_K`（重写上下文 Top-K）
- SQL：`DATABASE_URL`（用于校验/EXPLAIN/执行）
- 检索（两阶段+RRF融合）：
  - `TWO_STAGE_RETRIEVAL_ENABLED`（默认 1）
  - `RETRIEVE_STAGE1_TOP_K`（默认 12）
  - `RETRIEVE_WEIGHT_VECTOR`（默认 0.7）- 向量排序的RRF权重
  - `RETRIEVE_WEIGHT_GRAPH`（默认 0.3）- 图排序的RRF权重
- 时间过滤：
  - `TIME_REQUIRE_EXPLICIT`（默认 1）- 是否要求明确时间条件
  - `TIME_CONFIRM_DEFAULT`（默认 1）- 是否确认默认时间窗口
  - `DEFAULT_TIME_WINDOW_MONTHS`（默认 12）- 默认时间窗口月数
 - 嵌入/下载：
   - `EMBED_BACKEND`（默认 fastembed，可选 openai）
   - `EMBED_MODEL_NAME`（默认 BAAI/bge-small-zh-v1.5，用于 fastembed）
   - `HF_CACHE_DIR`（默认 ./.hf_cache，本地缓存目录）
   - `HF_ENDPOINT`（可选 HF 镜像，如 https://hf-mirror.com）
   - `FASTEMBED_THREADS`（默认 0 自动，设定 BLAS 线程数）
   - `OPENAI_EMBED_MODEL`（默认 text-embedding-3-small，用于 openai 后端）

## 环境与运行（推荐 uv）
优先使用 `uv` 来管理 Python 环境与运行（也可使用 `pip`，见上文）。
```bash
# 创建虚拟环境并安装依赖
uv venv
uv pip install -r requirements.txt

# 运行 CLI（示例）
uv run -m datainsight_agent.cli check
uv run -m datainsight_agent.cli run --question "本月 MAU 是多少？"
# 切换到 LlamaIndex 引擎
uv run -m datainsight_agent.cli run --question "本月 MAU 是多少？" --engine llamaindex
```

### 嵌入模型下载与加速（fastembed）
- 若遇到 HuggingFace 下载失败（如 SSL/EOF），可在 `.env` 或系统环境中设置镜像与缓存：
  - `HF_ENDPOINT=https://hf-mirror.com`
  - `HF_CACHE_DIR=.hf_cache`
  - 可选：`HF_HOME=.hf_cache`、`HF_DATASETS_CACHE=.hf_cache`、`TRANSFORMERS_CACHE=.hf_cache`
  - 控制线程：`FASTEMBED_THREADS=0`（自动）或具体数值
- Windows PowerShell 示例：
```powershell
$env:HF_ENDPOINT='https://hf-mirror.com'
$env:HF_CACHE_DIR='.hf_cache'
uv run -m datainsight_agent.cli rewrite --question "各渠道 MAU 对比"
```

## .env.example（建议）
将以下内容保存为项目根目录的 `.env.example`，并复制为 `.env` 后按需修改：
```dotenv
# LLM / OpenAI 兼容
OPENAI_API_KEY=
OPENAI_BASE_URL=

# 向量与嵌入
VECTOR_INDEX_DIR=vector_index
VECTOR_SPACE=ip
VECTOR_DIM=384
EMBED_BACKEND=fastembed  # fastembed | openai
EMBED_MODEL_NAME=BAAI/bge-small-zh-v1.5
HF_CACHE_DIR=.hf_cache
HF_ENDPOINT=
FASTEMBED_THREADS=0
OPENAI_EMBED_MODEL=text-embedding-3-small

# 元数据/图
GRAPH_BACKEND=local
LOCAL_GRAPH_PATH=kb_graph.sqlite
METADATA_DIR=metadata

# 数据仓库
WAREHOUSE_DIALECT=sqlite
DW_TABLE=dws_user_activity_monthly
DW_TIME_COLUMN=month
DATABASE_URL=sqlite:///./datainsight.db

# 时间策略
DEFAULT_TIME_WINDOW_MONTHS=12
TIME_REQUIRE_EXPLICIT=1
TIME_CONFIRM_DEFAULT=1

# Q2Q / RAG
LLM_Q2Q_ENABLED=1
LLM_Q2Q_TOP_K=6
RAG_TOP_K=5

# 两阶段检索 + RRF
TWO_STAGE_RETRIEVAL_ENABLED=1
RETRIEVE_STAGE1_TOP_K=12
RETRIEVE_WEIGHT_VECTOR=0.7
RETRIEVE_WEIGHT_GRAPH=0.3
```

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

## Timings 用法
打印编排节点（如 `deconstruct`、`retrieve`、`plan`、`build_ir`、`execute_or_respond`）的开始/结束时间与耗时（秒）：
```bash
python -m datainsight_agent.cli timings --question "今年各渠道的 MAU 对比"
# 输出：
# node    start_s end_s  duration_s
# node_deconstruct 0.000 0.250 0.250
# node_retrieve    0.251 0.420 0.169
# ...
```

## Q2Q（Query-to-Query 重写）配置
- `LLM_Q2Q_ENABLED`：是否启用 LLM+RAG 的重写（默认 1）
- `LLM_Q2Q_TOP_K`：重写阶段纳入的 KB 条目 Top-K（默认 6）
- 说明：当开启时，`deconstruct` 节点会并行触发 Q2Q 重写与概念抽取，以提升可扩展性与吞吐性能。
