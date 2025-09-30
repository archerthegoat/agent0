from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from datainsight_agent.config.settings import load_settings


@dataclass
class VectorStoreConfig:
    type: str  # milvus | local_hnsw
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    index_path: Optional[str] = None


@dataclass
class DatabaseConfig:
    type: str  # mysql | postgresql | sqlite
    url: str
    dialect: Optional[str] = None


@dataclass
class LLMConfig:
    provider: str  # qwen | openai
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class ConfigManager:
    """Centralized configuration facade built on top of existing settings."""

    def __init__(self) -> None:
        self._s = load_settings()

    def get_vector_config(self) -> VectorStoreConfig:
        # Reuse existing envs: prefer Milvus if configured, else local index
        db_name = getattr(self._s, "milvus_db", None) or "default"
        milvus_host = getattr(self._s, "milvus_host", None)
        milvus_port = getattr(self._s, "milvus_port", None)
        if milvus_host and milvus_port:
            return VectorStoreConfig(type="milvus", host=milvus_host, port=int(milvus_port), db_name=db_name)
        return VectorStoreConfig(type="local_hnsw", index_path=getattr(self._s, "vector_index_dir", "vector_index"))

    def get_database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            type=(getattr(self._s, "warehouse_dialect", "sqlite") or "sqlite"),
            url=self._s.database_url,
            dialect=getattr(self._s, "warehouse_dialect", None),
        )

    def get_llm_config(self) -> LLMConfig:
        # Map to Qwen by default since current project uses QwenClient
        return LLMConfig(
            provider=getattr(self._s, "llm_provider", "qwen"),
            api_key=getattr(self._s, "openai_api_key", None),  # reuse OPENAI_* for provider-agnostic
            base_url=getattr(self._s, "openai_base_url", None),
            model=getattr(self._s, "openai_model", None),
        )


