from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class Settings(BaseModel):
	"""Application settings loaded from environment variables.

	This class intentionally avoids pydantic-settings to keep dependencies minimal.
	Use `load_settings()` to read from `.env` via python-dotenv and construct this model.
	"""

	neo4j_uri: str = Field(default="bolt://localhost:7687")
	neo4j_username: str = Field(default="neo4j")
	neo4j_password: str = Field(default="changeme")

	# Local vector store (HNSW)
	vector_index_dir: str = Field(default="vector_index")
	vector_space: str = Field(default="ip")  # ip or l2
	vector_dim: int = Field(default=384)  # BGE small zh v1.5

	# Metric vector index directory (separate from general KB index)
	metric_index_dir: str = Field(default="metric_index")

	# Metadata directory (for KB JSON such as metrics/dimensions/intent_mappings)
	metadata_dir: str = Field(default="metadata")

	# Graph backend selection: local | neo4j | none
	graph_backend: str = Field(default="local")
	local_graph_path: str = Field(default="kb_graph.sqlite")

	log_level: str = Field(default="INFO")
	log_dir: str = Field(default="logs")

	openai_api_key: Optional[str] = Field(default=None)
	# Q2Q (LLM rewrite) feature flags
	llm_q2q_enabled: bool = Field(default=True)
	llm_q2q_top_k: int = Field(default=6)
	# LLM generation controls
	llm_temperature: float = Field(default=0.0)
	llm_max_tokens: int = Field(default=512)

	# Retrieval defaults
	rag_top_k: int = Field(default=5)
	# 是否在没有时间过滤时跳过检索（默认True，保持向后兼容）
	retrieve_skip_no_time: bool = Field(default=True)
	# 是否启用retrieve组件缓存机制（默认True，提高性能）
	retrieve_cache_enabled: bool = Field(default=True)

	# External backends feature flags (default disabled for local-only setups)
	es_enabled: bool = Field(default=False)
	milvus_enabled: bool = Field(default=False)
	neo4j_enabled: bool = Field(default=False)

	# Elasticsearch settings (used when es_enabled=True)
	es_hosts: str = Field(default="")  # comma-separated hosts
	es_index: str = Field(default="kb_docs")
	es_user: Optional[str] = Field(default=None)
	es_password: Optional[str] = Field(default=None)

	# Milvus settings (used when milvus_enabled=True)
	milvus_uri: str = Field(default="")
	milvus_db: str = Field(default="datainsight")
	milvus_collection: str = Field(default="kb_vectors")
	milvus_user: Optional[str] = Field(default=None)
	milvus_password: Optional[str] = Field(default=None)

	# Metric enrichment: whether to auto-enrich aggregation/filters for metrics not fully specified in metadata
	# 默认关闭，聚合/过滤完全以注册表(metadata/metrics.json)为准
	metric_enrichment_enabled: bool = Field(default=False)

	# Orchestrator engine: llamaindex | langgraph
	orchestrator_engine: str = Field(default="llamaindex")

	# Two-stage retrieval controls
	two_stage_retrieval_enabled: bool = Field(default=True)
	retrieval_top_k_stage1: int = Field(default=12)
	retrieval_weight_vector: float = Field(default=0.7)
	retrieval_weight_graph: float = Field(default=0.3)
	retrieval_overfetch: int = Field(default=3)
	retrieval_hnsw_ef: int = Field(default=64)
	retrieval_cache_ttl_seconds: int = Field(default=300)

	# Data warehouse/config-driven SQL defaults
	warehouse_dialect: str = Field(default="sqlite")  # sqlite | mysql | postgres | clickhouse | ...
	dw_table: str = Field(default="dws_user_activity_monthly")
	dw_time_column: str = Field(default="month")
	dw_partition_column: str = Field(default="")  # optional
	# DW semantic columns for enrichment (avoid hardcoding in code paths)
	dw_user_id_column: str = Field(default="user_id")
	active_flag_column: str = Field(default="active")
	# Comma-separated list of allowed columns; if empty, caller may probe or fallback
	dw_allowed_columns_csv: str = Field(default="")
	# Default time window in months for queries lacking explicit time
	default_time_window_months: int = Field(default=12)
	# Require explicit time? If true and no explicit/phrase time given, ask to clarify
	time_require_explicit: bool = Field(default=True)
	# Confirm applying default time window when explicit time missing
	time_confirm_default: bool = Field(default=True)

	# Optional SQL validation runtime target (e.g., sqlite:///./datainsight.db)
	database_url: Optional[str] = Field(default=None)
	
	# API endpoints configuration
	api_endpoints: Dict[str, str] = Field(default={
		"openai": "https://api.openai.com/v1",
		# Qwen (DashScope) OpenAI-compatible endpoint
		"qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1"
	})
	
	# Metadata files configuration
	metadata_files: Dict[str, str] = Field(default={
		"dimensions": "metadata/dimensions.json",
		"metrics": "metadata/metrics.json",
		"intent_mappings": "metadata/intent_mappings.json",
		"questions": "metadata/questions.json"
	})
	
	# Log files configuration
	log_files: Dict[str, str] = Field(default={
		"main": "datainsight_agent.log",
		"calls": "agent_calls.log"
	})
	
	# Default models configuration
	default_models: Dict[str, str] = Field(default={
		"embed_model": "BAAI/bge-small-zh-v1.5",
		"openai_embed_model": "text-embedding-3-small",
		# Default to Qwen2.5-72B-Instruct for OpenAI-compatible chat
		"qwen_model": "qwen2.5-72b-instruct"
	})
	
	# Default file paths configuration
	default_paths: Dict[str, str] = Field(default={
		"db_path": "datainsight.db",
		"log_path": "logs/datainsight_manual.log",
		"sqlite_path": "./datainsight.db",
		"kb_graph_path": "kb_graph.sqlite"
	})
	
	# Project information configuration
	project_info: Dict[str, str] = Field(default={
		"name": "DataInsight Agent",
		"description": "Enterprise-grade natural language data agent",
		"version": "0.5.0"
	})

	@validator("log_level")
	def _upper_log_level(cls, v: str) -> str:
		return v.upper()



def load_settings(env_path: Optional[Path] = None) -> Settings:
	"""Load settings from environment, supporting a local .env file.

	- Loads `.env` from project root by default if present.
	- Returns a validated `Settings` instance.
	"""
	# Ensure .env is loaded for local development
	load_dotenv(dotp_path := str(env_path) if env_path else None)
	# note: keep variable names stable to avoid breaking existing envs
	return Settings(
		neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
		neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
		neo4j_password=os.getenv("NEO4J_PASSWORD", "changeme"),
		vector_index_dir=os.getenv("VECTOR_INDEX_DIR", "vector_index"),
		vector_space=os.getenv("VECTOR_SPACE", "ip"),
		vector_dim=int(os.getenv("VECTOR_DIM", "384")),
		metric_index_dir=os.getenv("METRIC_INDEX_DIR", "metric_index"),
		metadata_dir=os.getenv("METADATA_DIR", "metadata"),
		graph_backend=os.getenv("GRAPH_BACKEND", "local"),
		local_graph_path=os.getenv("LOCAL_GRAPH_PATH", "kb_graph.sqlite"),
		log_level=os.getenv("LOG_LEVEL", "INFO"),
		log_dir=os.getenv("LOG_DIR", "logs"),
		orchestrator_engine=os.getenv("ORCHESTRATOR_ENGINE", "llamaindex"),
		openai_api_key=os.getenv("OPENAI_API_KEY"),
		llm_q2q_enabled=os.getenv("LLM_Q2Q_ENABLED", "1") not in {"0", "false", "False"},
		llm_q2q_top_k=int(os.getenv("LLM_Q2Q_TOP_K", "6")),
		llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
		llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
		rag_top_k=int(os.getenv("RAG_TOP_K", "5")),
		retrieve_skip_no_time=os.getenv("RETRIEVE_SKIP_NO_TIME", "1") not in {"0", "false", "False"},
		retrieve_cache_enabled=os.getenv("RETRIEVE_CACHE_ENABLED", "1") not in {"0", "false", "False"},
		es_enabled=os.getenv("ES_ENABLED", "0") not in {"0", "false", "False"},
		milvus_enabled=os.getenv("MILVUS_ENABLED", "0") not in {"0", "false", "False"},
		neo4j_enabled=os.getenv("NEO4J_ENABLED", "0") not in {"0", "false", "False"},
		es_hosts=os.getenv("ES_HOSTS", ""),
		es_index=os.getenv("ES_INDEX", "kb_docs"),
		es_user=os.getenv("ES_USER"),
		es_password=os.getenv("ES_PASSWORD"),
		milvus_uri=os.getenv("MILVUS_URI", ""),
		milvus_db=os.getenv("MILVUS_DB", "datainsight"),
		milvus_collection=os.getenv("MILVUS_COLLECTION", "kb_vectors"),
		milvus_user=os.getenv("MILVUS_USER"),
		milvus_password=os.getenv("MILVUS_PASSWORD"),
		metric_enrichment_enabled=os.getenv("METRIC_ENRICHMENT_ENABLED", "0") not in {"0", "false", "False"},
		warehouse_dialect=os.getenv("WAREHOUSE_DIALECT", "sqlite"),
		dw_table=os.getenv("DW_TABLE", "dws_user_activity_monthly"),
		dw_time_column=os.getenv("DW_TIME_COLUMN", "month"),
		dw_partition_column=os.getenv("DW_PARTITION_COLUMN", ""),
		dw_allowed_columns_csv=os.getenv("DW_ALLOWED_COLUMNS", ""),
		default_time_window_months=int(os.getenv("DEFAULT_TIME_WINDOW_MONTHS", "12")),
		time_require_explicit=os.getenv("TIME_REQUIRE_EXPLICIT", "1") not in {"0", "false", "False"},
		time_confirm_default=os.getenv("TIME_CONFIRM_DEFAULT", "1") not in {"0", "false", "False"},
		database_url=os.getenv("DATABASE_URL"),
		# Retrieval runtime tuning
		retrieval_overfetch=int(os.getenv("RETRIEVE_OVERFETCH", "3")),
		retrieval_hnsw_ef=int(os.getenv("RETRIEVE_HNSW_EF", "64")),
		retrieval_cache_ttl_seconds=int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "300")),
		# Default file paths
		default_paths={
			"db_path": os.getenv("DEFAULT_DB_PATH", "datainsight.db"),
			"log_path": os.getenv("DEFAULT_LOG_PATH", "logs/datainsight_manual.log"),
			"sqlite_path": os.getenv("DEFAULT_SQLITE_PATH", "./datainsight.db"),
			"kb_graph_path": os.getenv("DEFAULT_KB_GRAPH_PATH", "kb_graph.sqlite")
		},
		# Project information
		project_info={
			"name": os.getenv("PROJECT_NAME", "DataInsight Agent"),
			"description": os.getenv("PROJECT_DESCRIPTION", "Enterprise-grade natural language data agent"),
			"version": os.getenv("PROJECT_VERSION", "0.5.0")
		},
	)
