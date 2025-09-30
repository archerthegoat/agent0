from __future__ import annotations

from typing import List

from datainsight_agent.services.registry.metric_registry import MetricRegistry, MetricDef
from datainsight_agent.config.settings import load_settings
from datainsight_agent.clients.vector_store import EmbeddingModel
try:
    from datainsight_agent.clients.vector_store import MilvusVectorStore
except Exception:
    MilvusVectorStore = None
from pathlib import Path


class MetricRetriever:
    """度量检索：仅使用向量检索（Milvus），不再回退到模糊匹配。"""

    def __init__(self) -> None:
        # 延迟加载优化
        self._registry = None
        self._metrics = None
        self._emb: EmbeddingModel | None = None
        self._vec: MilvusVectorStore | None = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """延迟初始化，避免不必要的加载"""
        if self._initialized:
            return
        
        # 优化：缓存MetricRegistry实例
        if not hasattr(MetricRetriever, '_shared_registry'):
            MetricRetriever._shared_registry = MetricRegistry()
            MetricRetriever._shared_registry.load()
        
        self._registry = MetricRetriever._shared_registry
        
        # 优化：缓存metrics列表
        if not hasattr(MetricRetriever, '_shared_metrics'):
            seen: set[int] = set()
            MetricRetriever._shared_metrics: List[MetricDef] = []
            for m in getattr(self._registry, "_name_to_metric", {}).values():
                key = id(m)
                if key not in seen:
                    seen.add(key)
                    MetricRetriever._shared_metrics.append(m)
        
        self._metrics = MetricRetriever._shared_metrics
        
        # Vector index (Milvus) - 优化：缓存embedding模型
        try:
            s = load_settings()
            if MilvusVectorStore is None:
                raise RuntimeError("MilvusVectorStore not available. Please install pymilvus and ensure MILVUS_ENABLED=true")
            
            # 优化：缓存embedding模型
            if not hasattr(MetricRetriever, '_shared_emb'):
                MetricRetriever._shared_emb = EmbeddingModel()
            self._emb = MetricRetriever._shared_emb
            
            # 优化：缓存向量存储
            if not hasattr(MetricRetriever, '_shared_vec'):
                dim = getattr(s, "vector_dim", 384)
                MetricRetriever._shared_vec = MilvusVectorStore(dim=int(dim), space=str(getattr(s, "vector_space", "ip")))
            self._vec = MetricRetriever._shared_vec
        except Exception as e:
            print(f"[ERROR] MetricRetriever initialization failed: {e}")
            self._emb = None
            self._vec = None
        
        self._initialized = True

    def search(self, query: str, top_k: int = 3) -> List[MetricDef]:
        if not query:
            return []
        
        # 确保初始化
        self._ensure_initialized()
        
        # 1) Try vector search if available
        try:
            if self._emb and self._vec:
                vec = self._emb.embed([str(query)])[0]
                pairs = self._vec.search([vec], top_k=max(1, top_k))[0]
                # pairs: List[(id, dist)] with id stored as metric_id or canonical name
                # Build map from possible ids to MetricDef
                name_map = {}
                for m in self._metrics:
                    # prefer metric_id if present; else canonical
                    key = m.metric_id or m.canonical_name
                    name_map[str(key)] = m
                out: List[MetricDef] = []
                for _id, _dist in pairs:
                    md = name_map.get(str(_id))
                    if md and md not in out:
                        out.append(md)
                if out:
                    return out[: max(1, top_k)]
        except Exception:
            pass

        # 无回退：向量检索未命中时返回空列表
        return []


def build_metric_index(metadata_dir: str | Path = "metadata", index_dir: str | Path = "metric_index") -> int:
    """Build or rebuild a metric vector index from registry.

    - Embeds each metric using canonical_name + aliases joined as text
    - Stores vectors in MilvusVectorStore with meta-id = metric_id or canonical_name
    Returns number of indexed metrics.
    """
    if MilvusVectorStore is None:
        raise RuntimeError("MilvusVectorStore not available. Please install pymilvus and ensure MILVUS_ENABLED=true")
    
    reg = MetricRegistry(metadata_dir)
    reg.load()
    # unique MetricDefs
    seen: set[int] = set()
    metrics: List[MetricDef] = []
    for m in getattr(reg, "_name_to_metric", {}).values():
        key = id(m)
        if key not in seen:
            seen.add(key)
            metrics.append(m)
    emb = EmbeddingModel()
    texts: List[str] = []
    ids: List[str] = []
    metas: List[dict] = []
    for m in metrics:
        t = (m.canonical_name + " " + " ".join(m.aliases)).strip()
        if not t:
            continue
        texts.append(t)
        mid = m.metric_id or m.canonical_name
        ids.append(str(mid))
        metas.append({"id": str(mid), "canonical_name": m.canonical_name})
    if not texts:
        return 0
    vectors = emb.embed(texts)
    s = load_settings()
    store = MilvusVectorStore(dim=len(vectors[0]), space=str(getattr(s, "vector_space", "ip")))
    store.add(ids=ids, vectors=vectors, metadatas=metas)
    return len(ids)


