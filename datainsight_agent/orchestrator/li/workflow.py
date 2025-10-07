from __future__ import annotations

from typing import Any, Dict, Generator


class LIWorkflow:
    """Lightweight orchestrator (q2q -> retrieve -> plan -> build_ir -> execute),
    implemented with plain methods to keep a .stream(values) interface compatible
    with existing CLI. Internally使用 LlamaIndex 的检索包装，但不强依赖 Workflow 装饰器。
    """

    def __init__(self) -> None:
        pass

    def q2q(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter
        st = dict(state)
        q = str(st.get("question") or "").strip()
        if not q:
            return st
        try:
            rr = OptimizedQ2QRewriter().rewrite(q)
            st["q2q"] = rr.model_dump() if hasattr(rr, "model_dump") else rr
        except Exception:
            pass
        return st

    def retrieve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Use LlamaIndex native retriever wrapper + fusion; fallback to legacy service."""
        from datainsight_agent.config.settings import load_settings
        from datainsight_agent.services.retrieval import RetrievalService
        from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel
        from datainsight_agent.clients.graph_client import LocalGraphClient
        from pathlib import Path
        st = dict(state)
        try:
            # Build legacy service (as data source) once
            s = load_settings()
            vector_store = None
            local_graph = None
            if getattr(s, "milvus_enabled", False):
                emb = EmbeddingModel()
                dim = len(emb.embed(["__probe__"])[0])
                vector_store = MilvusVectorStore(dim=dim, space=str(s.vector_space))
            gpath = Path(s.local_graph_path)
            if gpath.exists():
                local_graph = LocalGraphClient(str(gpath))
            legacy = RetrievalService(vector_store=vector_store, local_graph=local_graph)

            # Wrap legacy as a LlamaIndex BaseRetriever
            try:
                from llama_index.core.retrievers import BaseRetriever
                from llama_index.core.schema import TextNode, NodeWithScore

                class _KBWrapperRetriever(BaseRetriever):  # type: ignore
                    def __init__(self, svc: RetrievalService, top_k: int = 5) -> None:
                        self._svc = svc
                        self._top_k = top_k

                    def _retrieve(self, query: str):  # type: ignore
                        concepts = []
                        # very light concept extraction from q2q if available in outer scope
                        # this retriever is used immediately below; query carries user text
                        ents = self._svc.hybrid_knowledge_retriever(concepts, top_k=self._top_k)
                        nodes = []
                        for e in ents:
                            meta = {
                                "id": getattr(e, "id", ""),
                                "canonical_name": getattr(e, "canonical_name", ""),
                                "type": getattr(e, "type", ""),
                            }
                            txt = f"{meta.get('canonical_name')} ({meta.get('type')})"
                            node = TextNode(text=txt, metadata=meta)
                            nodes.append(NodeWithScore(node=node, score=1.0))
                        return nodes

                # Compose fusion retriever (single sub-retriever for now)
                from llama_index.core.retrievers import QueryFusionRetriever
                top_k = max(3, int(getattr(s, "rag_top_k", 5)))
                sub = _KBWrapperRetriever(legacy, top_k=top_k)
                fused = QueryFusionRetriever(retrievers=[sub], similarity_top_k=top_k, num_queries=1)

                qtxt = str(st.get("question") or "")
                li_nodes = fused.retrieve(qtxt)
                # Map LI nodes -> kb_entities (compat downstream)
                out = []
                for nws in li_nodes:
                    m = getattr(getattr(nws, "node", None), "metadata", {}) or {}
                    out.append(m)
                st["kb_entities"] = out
            except Exception:
                # Fallback to legacy path directly
                concepts = list((st.get("q2q") or {}).get("concepts") or [])
                st["kb_entities"] = legacy.hybrid_knowledge_retriever(concepts, top_k=max(3, int(getattr(s, "rag_top_k", 5))))
        except Exception:
            st["kb_entities"] = []
        return st

    def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from datainsight_agent.config.settings import load_settings
        from datainsight_agent.services.registry.metric_registry import MetricRegistry
        from datainsight_agent.services.parsers.time_filter_parser import parse_time_filter
        st = dict(state)
        try:
            s = load_settings()
            q2q = st.get("q2q") or {}
            qtxt = str(st.get("question") or "")
            mr = MetricRegistry()
            has_metric = mr.resolve_from_signals([qtxt]) is not None
            time_required = bool(getattr(s, "time_require_explicit", False))
            has_time = True
            if time_required:
                has_time = bool(str(q2q.get("time_filter") or "").strip())
                if not has_time:
                    tf = parse_time_filter("", qtxt, getattr(s, "dw_time_column", "month") or "month")
                    has_time = tf is not None
            st["plan"] = "execute_sql" if has_metric and (has_time or not time_required) else "clarify"
        except Exception:
            st["plan"] = "clarify"
        return st

    def build_ir(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from datainsight_agent.models.ir import SemanticQueryIR
        from datainsight_agent.services.parsers.dimension_parser import parse_dimensions
        from datainsight_agent.services.parsers.metric_parser import parse_metrics, parse_metric_filters
        from datainsight_agent.services.parsers.time_filter_parser import parse_time_filter
        from datainsight_agent.config.settings import load_settings
        st = dict(state)
        ir = SemanticQueryIR()
        try:
            ir.group_by = parse_dimensions(st)
            ir.aggregations = parse_metrics(st)
            ir.filters.extend(parse_metric_filters(st))
            s = load_settings()
            time_col = getattr(s, "dw_time_column", "month") or "month"
            q2q = st.get("q2q") or {}
            tf_raw = str(q2q.get("time_filter") or "").strip()
            tf = parse_time_filter(tf_raw, str(st.get("question") or ""), time_col)
            if tf:
                ir.filters.append(tf)
        except Exception:
            pass
        st["ir_obj"] = ir
        st["ir"] = ir.model_dump() if hasattr(ir, "model_dump") else str(ir)
        return st

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from datainsight_agent.services.core.sql_generator import SQLGenerator
        from datainsight_agent.services.sql_validator import SQLValidator
        from datainsight_agent.services.core.sql_executor import SQLExecutor
        from datainsight_agent.config.settings import load_settings
        st = dict(state)
        try:
            s = load_settings()
            sql = SQLGenerator(database_url=s.database_url).generate(st.get("ir_obj"))
            st["sql"] = sql
            val = SQLValidator().validate(sql, database_url=s.database_url, do_explain=bool(s.database_url))
            st["validation"] = val.model_dump()
            if s.database_url:
                st["rows"] = SQLExecutor(s).execute(sql, limit=10)
        except Exception as e:
            st["exec_error"] = str(e)
        return st


def build_workflow() -> LIWorkflow:
    return LIWorkflow()


def _run_seq(agent: LIWorkflow, state: Dict[str, Any]) -> Dict[str, Any]:
    st = dict(state)
    st = agent.q2q(st)
    st = agent.retrieve(st)
    st = agent.plan(st)
    st = agent.build_ir(st)
    st = agent.execute(st)
    return st


# Provide a stream API compatible with pipeline
def _stream_values(agent: LIWorkflow, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    yield _run_seq(agent, state)

# Monkey-patch LIWorkflow to have .stream similar to pipeline
def _li_stream(self: LIWorkflow, state: Dict[str, Any], stream_mode: str = "values"):
    return _stream_values(self, state)

setattr(LIWorkflow, "stream", _li_stream)


