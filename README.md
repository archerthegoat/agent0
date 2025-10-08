# DataInsight Agent

English | 中文

## Overview
DataInsight Agent is an enterprise-grade, natural-language-driven data agent. It turns business questions into precise SQL via a Text-to-IR-to-SQL pipeline, grounded on a hybrid knowledge base: a Milvus vector store for semantic retrieval and a lightweight SQLite-based graph for structured knowledge. Orchestration is built with LlamaIndex (QueryPipeline + FnComponent). The agent includes an explicit IR (intermediate representation) layer and removes direct LLM SQL fallback for safety and transparency.

## Features
- Text-to-IR-to-SQL pipeline with safety-first generation (no direct LLM SQL fallback)
- **Enhanced RAG System**: Adaptive relevance calculation, dynamic pattern generation, intelligent entity type inference
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
## Workflow (LlamaIndex)
python -m datainsight_agent.cli run --question "What is monthly active users?" --validate --execute
```

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
   │  ├─ settings.py
   │  └─ keyword_mappings.py
   ├─ common/
   │  └─ logging.py
   ├─ models/
   │  ├─ kb.py
   │  └─ ir.py
   ├─ clients/
   │  ├─ graph_client.py
   │  └─ vector_store.py
   ├─ services/
   │  ├─ core/                    # Core services with enhanced RAG
   │  │  ├─ query_rewriter.py
   │  │  ├─ sql_generator.py
   │  │  ├─ sql_executor.py
   │  │  ├─ enhanced_kb_vector_retriever.py
   │  │  ├─ adaptive_relevance_calculator.py
   │  │  ├─ dynamic_pattern_generator.py
   │  │  ├─ intelligent_entity_type_inferencer.py
   │  │  ├─ type_aware_retrieval_strategy.py
   │  │  └─ metadata_loader.py
   │  ├─ parsers/
   │  │  ├─ metric_parser.py
   │  │  ├─ dimension_parser.py
   │  │  └─ time_filter_parser.py
   │  ├─ registry/
   │  │  ├─ metric_registry.py
   │  │  └─ metric_retriever.py
   │  └─ llm.py
   ├─ orchestrator/
   │  └─ li/
   │     ├─ __init__.py
   │     └─ workflow.py
   └─ etl/
      └─ ragflow_etl.py
```

## Architecture
The agent follows a modular architecture with clear separation of concerns:

- **Core Services**: Enhanced RAG system with adaptive relevance calculation and intelligent entity type inference
- **Orchestration**: LlamaIndex Workflow (q2q→retrieve→plan→build_ir→execute)
- **Knowledge Base**: Hybrid vector store (HNSW) + SQLite graph
- **Safety**: No direct LLM SQL fallback, explicit IR layer for transparency

### Key Components
- `services/core/`: Core services with enhanced RAG capabilities
- `orchestrator/li/`: LlamaIndex Workflow orchestration
- `parsers/`: Metric, dimension, and time filter parsing
- `registry/`: Metric registry and retrieval services

## Safety & Compliance
- Sensitive credentials are managed strictly via environment variables. No hard-coded secrets.
- Destructive operations (e.g., ETL writes) require explicit confirmation (`--yes`).
- Structured logs are written to `logs/` with timestamps and levels.

## Roadmap
- Enrich IR and SQL generation with robust validation
- Optional pluggable backends for remote graph/vector stores
- Expand LLM tool choices and provider abstractions

---


## CLI Commands
Essential commands for running the agent:

- `run`: Execute the full agent pipeline (Text→IR→SQL)
- `check`: Environment health checks
- `etl`: Offline ETL for metadata ingestion
- `metrics-index`: Build/rebuild metric vector index
- `timings`: Performance analysis of pipeline stages

For complete command reference, see `ENVIRONMENT_VARIABLES_GUIDE.md`.
