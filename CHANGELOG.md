# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.1.0] - 2025-09-05
### Added
- Initial project scaffold for DataInsight Agent.
- README, .env.example, requirements, .gitignore, logs/.
- Python package with config, logging, models, clients, services, orchestrator skeleton, ETL wrapper, and CLI.

## [0.2.0] - 2025-09-08
### Changed
- Replaced Milvus/Neo4j backends with local HNSW vector store and SQLite-based graph.
- Renamed clients to `clients/vector_store.py` and `clients/graph_client.py`.
- Updated ETL to build HNSW index and upsert entities into local graph.
- Updated retrieval to use HNSW + local graph hybrid.
- Adjusted README to reflect new architecture and configuration.

### Removed
- Removed `datainsight_agent/clients/milvus_client.py` and `datainsight_agent/clients/neo4j_client.py`.

## [0.3.0] - 2025-09-09
### Added
- Introduced explicit IR layer and `build_ir` node; added IR printout in CLI.
- New CLI: `rewrite` to inspect RAG + LLM rewrite without execution.
- Tools: `_tools/rewrite_preview.py`, `_tools/preview_sql.py`, `_tools/batch_rewrite.py`, `_tools/extract_rewrite.py`.
- DW-lite schema expanded with 8 new dimensions: `device_model, os_version, country, city, network_type, channel_subtype, ab_bucket, user_segment`.
- Synthetic seeder updated to generate new dimensions (LLM-backed with local fallback).

### Changed
- Removed direct LLM SQL fallback in CLI; agent reports error when IR/KB is insufficient.
- Orchestrator switched to IR→SQL generation path by default.

### Fixed
- Minor prompts and retrieval robustness improvements.

## [0.4.0] - 2025-09-10
### Added
- Q2Q（LLM+RAG）重写引入到 `node_deconstruct`，并提供 `LLM_Q2Q_ENABLED`、`LLM_Q2Q_TOP_K` 配置。
- `timings` 子命令：输出各编排节点耗时，辅助性能分析。
- `observe` 子命令：单次运行中同时观测 RAG 重写（向量召回/上下文/Prompt/重写结果）与完整编排（Plan/IR/SQL/校验/执行）及 timings。
- 文档：统一 CLI 子命令列表、日志与 timings 用法、`.env.example` 更新。
- 度量向量化检索（Metric Vector Search）：新增 `metric_index_dir` 配置、`metrics-index` CLI 用于构建/重建度量向量索引；`MetricRetriever` 采用 HNSW（无模糊回退）。
 - 优化开关：`DECONSTRUCT_SKIP_CONCEPTS_WHEN_Q2Q`、`DECONSTRUCT_SKIP_LLM_ON_CONFIDENT`、`TIME_REQUIRE_EXPLICIT`、`RETRIEVE_CONFIDENCE_GATE`。

### Changed
- 在 `node_deconstruct` 并行执行 Q2Q 与概念抽取，降低端到端延迟。
- 将 CLI 中合成数据（LLM 生成）逻辑抽离为 `services/synthetic_data.py` 并由 `db-seed-synthetic` 调用。
- `services/metric_retriever.py` 重构：添加向量检索路径并兼容回退；新增构建函数 `build_metric_index()`。
 - `orchestrator/graph.py`：
   - `node_deconstruct` 支持向量高置信门控，命中时可跳过 LLM；支持在 Q2Q 启用时按配置跳过独立概念抽取。
   - `node_build_ir` 强化时间策略：若开启 `TIME_REQUIRE_EXPLICIT` 且未提供明确时间窗口，则进入澄清而非套默认窗口。

### Fixed
- 若 LLM 不可用或返回非结构化数据，合成数据生成自动回退到本地生成器。

## [0.4.1] - 2025-09-11
### Fixed
- `observe`：当 Q2Q 返回缺失时间窗口或占位符 `YYYY-MM,YYYY-MM`（即便未显式标记 `clarify`）时，强制触发仅询问时间范围的二次问询；未填写则终止 SQL 生成，避免继续执行产生占位符时间的 SQL。

## [0.4.2] - 2025-09-11
### Changed
- Q2Q 反硬编码改造：
  - `prompts.q2q_prompt` 不再在异常分支使用固定表名/时间列/允许列兜底，严格读取配置；`group_by` 概念映射改为从 `metadata/intent_mappings.json` 动态加载。
  - `q2q.Q2QRewriter` 读取 `Settings.metadata_dir`，同时将 `top_k`、metric 检索 Top-K 来自配置（`LLM_Q2Q_TOP_K`、`LLM_Q2Q_METRIC_TOP_K`）。
  - 移除系统提示中的“Preferred metric names (canonical/aliases)”清单，避免任何度量先验硬编码。

## [0.4.3] - 2025-09-12
### Added
- TIME_CONFIRM_DEFAULT 配置：缺少时间时是否弹出确认默认时间窗口。
- 嵌入/下载配置：EMBED_BACKEND、EMBED_MODEL_NAME、HF_CACHE_DIR、HF_ENDPOINT、FASTEMBED_THREADS、OPENAI_EMBED_MODEL。
- CLI 交互增强：拒绝默认窗口后可输入时间与指标并继续执行。

### Changed
- 向量客户端：支持 HF 镜像与缓存，fastembed 失败时回退 OpenAI 嵌入；兜底零向量维度改为 `settings.vector_dim`。
- README：新增嵌入配置说明与 `.env.example` 示例。

## [0.5.0] - 2025-09-16
### Added
- 引入 LlamaIndex 作为主要编排引擎：新增 `datainsight_agent/orchestrator/li/` 骨架与 `build_pipeline()`。
- 配置：新增 `ORCHESTRATOR_ENGINE` 环境变量与 `Settings.orchestrator_engine`（默认 `llamaindex`）。
- 依赖：`llama-index`。

### Changed
- README：更新引擎说明与运行示例，默认使用 LlamaIndex。
- LlamaIndex 管道：检索阶段调用 `RetrievalService.hybrid_knowledge_retriever`，并通过 `QueryPipeline` + `FnComponent` 串联；不可用时顺序执行本地组件。
- CLI：移除 `compare-engines` 命令；`run/timings/observe` 全量改为 LlamaIndex 路径；去除对 LangGraph 的回退逻辑。

## [0.5.1] - 2025-09-22
### Changed
- CLI：移除顶层对 FastAPI 的导入，改为在 `api` 子命令内延迟导入，避免非 API 命令强依赖 FastAPI。
- README：简化配置段，改为链接 `ENVIRONMENT_VARIABLES_GUIDE.md`，减少重复。
- ENVIRONMENT_VARIABLES_GUIDE：修复失效文档链接，指向实际存在的文件名。

### Added
- `.env.example`：新增至仓库根目录，作为环境模板（与 README 中示例一致）。

## [0.5.2] - 2025-09-23
### Added
- 可选后端开关（默认关闭，安全回退）：`ES_ENABLED`、`MILVUS_ENABLED`、`NEO4J_ENABLED` 与相关连接配置，便于未来接入 Polyglot（ES/Milvus/Neo4j）。
- CLI 索引工具：`db-create-indexes`（支持 `--table/--dialect/--skip-optional`）、`db-show-indexes`、`db-drop-indexes --yes`。
- CLI 统一输出参数：`--json`、`--no-color`（已接入 `run/observe/sql-preview`）。
- 检索层：向量检索 TTL 缓存（`RETRIEVAL_CACHE_TTL_SECONDS`，默认 300s）。
- 检索融合观测：RRF 融合前/后 TopK 与权重日志（结构化日志 `rrf_fusion`）。
- 运行追踪：为 CLI 命令引入 `trace_id`（`logs/agent_calls.log`）与统一错误字段（`error_code/error_message/error_detail`）。

### Changed
- `observe` 子命令将 `show_prompt` 默认改为 `False`，便于在 `--json` 下获得纯净输出。
- `ENVIRONMENT_VARIABLES_GUIDE.md` 增补检索/后端相关开关与示例。

### Fixed
- `db-show-indexes` 兼容 SQLAlchemy Row 的 `_mapping` 输出，修复在不同方言/驱动下的打印异常。

## [0.6.0] - 2025-10-07
### Added
- LlamaIndex Workflow：新增 `datainsight_agent/orchestrator/li/workflow.py`（q2q→retrieve→plan→build_ir→execute）。
- LlamaIndex 工具：`datainsight_agent/tools/llamaindex_tools.py`（浅RAG指标召回/IR&SQL/校验等）。

### Changed
- CLI `run`：优先使用 Workflow，失败回退到旧 pipeline。
- README：更新为使用 `run`（Workflow），移除 `run-li-agent` 示例。

### Removed
- CLI：移除 `run-li-agent` 子命令（统一到 `run`）。
