from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from datainsight_agent.services.llm import QwenClient
from datainsight_agent.config.settings import load_settings
# from datainsight_agent.services.prompts import q2q_prompt  # 未使用，单拍式调用不需要
from datainsight_agent.services.kb_vector_index import KBVectorRetriever
# MetricRetriever 依赖已移除，度量由注册表解析，Q2Q 不再尝试检索度量列表


class Q2QRewrite(BaseModel):
    rewritten_question: Optional[str] = None
    metric: List[str] = []
    group_by: List[str] = []
    time_filter: Optional[str] = None
    concepts: List[str] = []
    clarify: bool = False
    ask: Optional[str] = None


class Q2QRewriter:
    """LLM+RAG Query-to-Query rewriter for fuzzy inputs.

    Returns compact structured hints for metric/group_by/time.
    """

    def __init__(self, metadata_dir: str | None = None) -> None:
        from datainsight_agent.config.settings import load_settings
        s = load_settings()
        self._metadata_dir = metadata_dir or s.metadata_dir
        # 延迟初始化KB向量检索器，避免不必要的加载
        self._kb_retriever = None
        self._kb_retriever_initialized = False

    def _get_kb_retriever(self):
        """懒加载KB向量检索器，使用类级缓存避免重复初始化"""
        if not self._kb_retriever_initialized:
            try:
                # 使用类级缓存，避免重复创建KBVectorRetriever实例
                if not hasattr(Q2QRewriter, '_shared_kb_retriever'):
                    Q2QRewriter._shared_kb_retriever = KBVectorRetriever("kb_vector_index")
                self._kb_retriever = Q2QRewriter._shared_kb_retriever
            except Exception:
                self._kb_retriever = None
            self._kb_retriever_initialized = True
        return self._kb_retriever
    
    def _kb_context(self, question: str, top_k: int) -> str:
        """使用向量索引快速构建KB上下文"""
        lines: List[str] = []
        
        try:
            # 懒加载向量检索器
            kb_retriever = self._get_kb_retriever()
            if not kb_retriever:
                return self._kb_context_fallback(question, top_k)
            
            # 使用向量检索获取相关实体，大幅减少上下文长度
            results = kb_retriever.search(question, top_k=max(1, top_k//4))
            
            # 构建超极简上下文，只保留最核心信息
            for result in results[:3]:  # 只保留前3个结果
                metadata = result["metadata"]
                entity_type = metadata.get("entity_type", "")
                canonical_name = metadata.get("canonical_name", "")

                if entity_type == "dimension":
                    column = metadata.get("column", "")
                    if column:
                        lines.append(f"{canonical_name}->{column}")
                    else:
                        lines.append(canonical_name)
                elif entity_type == "metric":
                    lines.append(canonical_name)
                elif entity_type == "mapping":
                    phrases = metadata.get("phrases", [])[:1]  # 只保留第一个短语
                    column = metadata.get("column", "")
                    if phrases and column:
                        lines.append(f"{phrases[0]}->{column}")
            
        except Exception as e:
            try:
                from datainsight_agent.common.logging import get_logger
                get_logger("q2q").warning("kb_retriever_fallback", error=str(e))
            except Exception:
                pass
            # 回退到传统方法
            return self._kb_context_fallback(question, top_k)
        
        # 添加可用的列名列表
        try:
            from datainsight_agent.config.settings import load_settings
            s = load_settings()
            allowed_cols = [c.strip() for c in (s.dw_allowed_columns_csv or "").split(",") if c.strip()]
            if not allowed_cols and s.database_url and s.warehouse_dialect.lower() == "sqlite":
                from sqlalchemy import create_engine, text as _text
                engine = create_engine(s.database_url)
                with engine.connect() as conn:
                    rows = conn.execute(_text(f"PRAGMA table_info({s.dw_table})")).fetchall()
                    allowed_cols = [str(r[1]) for r in rows]
            if allowed_cols:
                lines.append(f"available_columns: {', '.join(allowed_cols)}")
        except Exception:
            pass
            
        return "\n".join(lines)
    
    def _kb_context_fallback(self, question: str, top_k: int) -> str:
        """传统的KB上下文构建方法（回退方案）"""
        lines: List[str] = []
        ql = (question or "").lower()

        def _overlap_score(q: str, tokens: List[str]) -> float:
            q_words = set([w for w in q.replace("/", " ").replace("-", " ").split() if w])
            t_words: set[str] = set()
            for t in tokens:
                for w in str(t).lower().replace("/", " ").replace("-", " ").split():
                    if w:
                        t_words.add(w)
            if not q_words or not t_words:
                return 0.0
            inter = len(q_words & t_words)
            return inter / max(1, len(q_words))

        # 1) Knowledge entities（维度/概念）
        dim_rank: List[tuple[float, object]] = []
        try:
            from datainsight_agent.models.kb import KBEntity
            from pathlib import Path
            import json as _json
            md = Path(self._metadata_dir)
            ents: List[KBEntity] = []
            if md.exists():
                for p in sorted(md.glob("*.json")):
                    obj = _json.loads(p.read_text(encoding="utf-8"))
                    arr = obj if isinstance(obj, list) else [obj]
                    for it in arr:
                        try:
                            ents.append(KBEntity(**it))
                        except Exception:
                            continue
            # 计算维度相关性分数
            for e in ents:
                texts: List[str] = [e.canonical_name] + list(e.aliases)
                if e.what and e.what.description:
                    texts.append(e.what.description)
                score = _overlap_score(ql, texts)
                # 仅对维度/概念类型赋分
                et = (getattr(e, "type", "") or "").lower()
                if et in {"dimension", "concept", ""}:
                    dim_rank.append((score, e))
            # Top-K 维度（按分数）
            dim_rank.sort(key=lambda x: x[0], reverse=True)
            dim_quota = max(1, int(top_k * 0.5))
            for _, e in dim_rank[:dim_quota]:
                ds = e.how.data_source if (e.how and e.how.data_source) else None
                aliases = "|".join(e.aliases)
                if ds and ds.column:
                    lines.append(f"dimension: {e.canonical_name} (aliases: {aliases}) -> column: {ds.column}")
                else:
                    lines.append(f"concept: {e.canonical_name} (aliases: {aliases})")
        except Exception:
            pass
        
        # 2) 移除度量检索：度量解析由注册表驱动，这里不再拼接度量上下文
        
        # 3) 意图映射（短语→列）
        map_rank: List[tuple[float, tuple[str, str]]] = []
        try:
            from pathlib import Path as _P
            import json as _j
            # 使用配置化的文件路径
            from datainsight_agent.config.settings import load_settings
            s = load_settings()
            mp = _P("metadata") / s.metadata_files.get("intent_mappings", "intent_mappings.json")
            if mp.exists():
                obj = _j.loads(mp.read_text(encoding="utf-8"))
                maps = [m for m in (obj.get("group_by") or []) if isinstance(m, dict)]
                for m in maps:
                    phr = "/".join([str(x) for x in (m.get("phrases") or [])])
                    col = str(m.get("column") or "")
                    if phr and col:
                        sc = _overlap_score(ql, [phr])
                        if sc > 0.0:
                            map_rank.append((sc, (phr, col)))
                map_rank.sort(key=lambda x: x[0], reverse=True)
                map_quota = max(1, int(top_k * 0.2))
                for _, (phr, col) in map_rank[:map_quota]:
                    lines.append(f"mapping: {phr} -> {col}")
        except Exception:
            pass
        
        # 4) 添加可用的列名列表（从配置或数据库探测）
        try:
            from datainsight_agent.config.settings import load_settings
            s = load_settings()
            allowed_cols = [c.strip() for c in (s.dw_allowed_columns_csv or "").split(",") if c.strip()]
            if not allowed_cols and s.database_url and s.warehouse_dialect.lower() == "sqlite":
                from sqlalchemy import create_engine, text as _text
                engine = create_engine(s.database_url)
                with engine.connect() as conn:
                    rows = conn.execute(_text(f"PRAGMA table_info({s.dw_table})")).fetchall()
                    allowed_cols = [str(r[1]) for r in rows]
            if allowed_cols:
                lines.append(f"available_columns: {', '.join(allowed_cols)}")
        except Exception:
            pass
            
        return "\n".join(lines)

    def rewrite(self, question: str, top_k: int | None = None) -> Q2QRewrite:
        s = load_settings()
        if top_k is None:
            top_k = int(getattr(s, "llm_q2q_top_k", 6))
        # If no API key configured, return empty hints (caller should fallback)
        if not (__import__("os").getenv("QWEN_API_KEY") or __import__("os").getenv("DASHSCOPE_API_KEY") or s.openai_api_key):
            return Q2QRewrite()

        # 优化：提前检查是否需要LLM调用
        import os
        if os.getenv("LLM_Q2Q_ENABLED") == "0":
            return Q2QRewrite()
        
        # 单拍式：直接结构化生成（函数调用），失败回退纯文本 JSON 解析
        client = QwenClient(s)
        
        # 优化：并行构建KB上下文和初始化LLM
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            kb_future = executor.submit(self._kb_context, question, top_k)
            # LLM客户端已经在上面初始化，这里不需要额外的future
            kb_ctx = kb_future.result()

        # 超极简JSON Schema，只保留核心字段
        ultra_minimal_schema = {
            "type": "object",
            "properties": {
                "metric": {"type": "array"},
                "group_by": {"type": "array"},
                "time_filter": {"type": "string"},
                "concepts": {"type": "array"}
            },
            "required": ["metric", "group_by", "concepts"],
            "additionalProperties": False,
        }
        
        # 极简提示词，只保留问题，KB上下文作为注释
        simple_prompt = f"# {kb_ctx}\n{question}"
        
        try:
            obj = client.tool_call(
                system="",  # 完全移除系统提示词
                user=simple_prompt,
                tool_name="q2q_rewrite",
                json_schema=ultra_minimal_schema,
            )
        except Exception:
            obj = {}

        # 失败回退：纯文本 JSON 解析
        if not isinstance(obj, dict) or not obj:
            try:
                text = client.generate_sql(simple_prompt)
                import json as _json
                obj = _json.loads(text)
            except Exception:
                obj = {}

        out = Q2QRewrite()
        try:
            # 简化处理，只保留核心字段
            out.rewritten_question = question  # 使用原始问题作为重写问题
            out.metric = [str(x) for x in (obj.get("metric") or []) if isinstance(x, (str, int, float))]
            out.group_by = [str(x) for x in (obj.get("group_by") or []) if isinstance(x, (str, int, float))]
            tf = obj.get("time_filter")
            out.time_filter = str(tf) if tf else None
            out.concepts = [str(x) for x in (obj.get("concepts") or []) if isinstance(x, (str, int, float))]
            # 时间与指标早期澄清（Q2Q阶段）
            # 1) 指标澄清：若 Q2Q 给出的 metric 未通过注册表精确匹配，则改为澄清（不继续下游）
            
            # 早期校验：若 Q2Q 给出的 metric 未通过注册表精确匹配，则改为澄清（不继续下游）
            from datainsight_agent.services.metric_registry import MetricRegistry
            reg = MetricRegistry()
            matched = False
            # 先校验 LLM 产出的 metric
            for m in (out.metric or []):
                if reg.resolve_from_signals([str(m)]):
                    matched = True
                    break
            # 若未命中，直接对原始问题进行注册表解析（更稳妥的 general 路径）
            if not matched:
                mdef = reg.resolve_from_signals([question])
                if mdef is not None:
                    matched = True
                    out.metric = [mdef.canonical_name]
            if not matched:
                out.clarify = True
                out.ask = "请补充指标（例如：MAU/UV/PV）。"
                out.metric = []  # 避免误用无效 metric
            
            # 2) 时间澄清：若配置要求显式时间，则必须在原始问题中出现明确时间范围
            #    - 若 Q2Q 产出了 time_filter 但原始问题未包含时间，则仍要求澄清
            try:
                s2 = load_settings()
                require_time = bool(getattr(s2, "time_require_explicit", True))
            except Exception:
                require_time = True
            if require_time:
                import re as _re
                qtxt = question or ""
                # 判断原始问题是否包含明确的 YYYY-MM,YYYY-MM 或 2025-06 到 2025-08 形式
                has_explicit = bool(_re.search(r"\d{4}-\d{2}\s*(?:到|~|–|-|—|\.{2}|,|，)\s*\d{4}-\d{2}", qtxt))
                if not has_explicit:
                    # 无论 LLM 是否给出 time_filter，都要求用户澄清时间
                    out.time_filter = None
                    out.clarify = True
                    msg = "请补充时间范围（YYYY-MM,YYYY-MM）。"
                    if out.ask and "指标" in out.ask:
                        out.ask = out.ask + " 另外，" + msg
                    else:
                        out.ask = (out.ask or msg)
        except Exception:
            return Q2QRewrite()
        return out


