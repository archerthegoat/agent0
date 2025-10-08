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
        """Use enhanced RAG system for retrieval."""
        from datainsight_agent.config.settings import load_settings
        from datainsight_agent.services.core.enhanced_kb_vector_retriever import EnhancedKBVectorRetriever
        st = dict(state)
        try:
            s = load_settings()
            
            # Use enhanced RAG system
            enhanced_retriever = EnhancedKBVectorRetriever("kb_vector_index")
            qtxt = str(st.get("question") or "")
            top_k = max(3, int(getattr(s, "rag_top_k", 5)))
            
            # Get enhanced retrieval result
            enhanced_result = enhanced_retriever.search_with_enhanced_rag(qtxt, top_k)
            fragments = enhanced_result.get('fragments', [])
            
            # Convert fragments to kb_entities format for compatibility
            kb_entities = []
            for fragment in fragments:
                metadata = fragment.get('metadata', {})
                kb_entity = {
                    'id': fragment.get('entity_id', ''),
                    'canonical_name': metadata.get('canonical_name', ''),
                    'type': fragment.get('entity_type', ''),
                    'score': fragment.get('score', 0.0)
                }
                kb_entities.append(kb_entity)
            
            st["kb_entities"] = kb_entities
        except Exception as e:
            print(f"[WARN] Enhanced RAG retrieval failed: {e}")
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


