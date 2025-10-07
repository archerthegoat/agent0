"""
LEGACY: Original metric parser used by the pipeline.

Direct implementation of metric parsing logic.
"""

from typing import Dict, Any, List, Optional
from datainsight_agent.models.ir import SemanticAggregation, SemanticFilter
from datainsight_agent.config.keyword_mappings import (
    METRIC_KEYWORDS, AGGREGATION_MAPPING
)


class MetricParser:
    """度量解析器"""
    
    def __init__(self):
        self._resolved_metric_def = None  # 缓存本轮解析得到的 MetricDef
    
    def parse_metrics(self, state: Dict[str, Any]) -> List[SemanticAggregation]:
        """
        解析度量并返回聚合函数列表
        
        Args:
            state: 管道状态
            
        Returns:
            聚合函数列表
        """
        question = str(state.get("question") or "").lower()
        
        # 1) 优先通过 Registry/RAG 解析结构化度量定义（聚合+过滤）
        self._resolved_metric_def = None
        metric_def = self._resolve_metric_def(state)
        if metric_def and metric_def.aggregation:
            self._resolved_metric_def = metric_def
            agg = metric_def.aggregation or {}
            # 严格使用注册表中的 alias（不改写大小写），确保 SQL 列名稳定
            alias_value = str(agg.get("alias") or (metric_def.metric_id or metric_def.canonical_name)).strip()
            return [SemanticAggregation(
                function=str(agg.get("function") or "").upper() or "COUNT",
                field=str(agg.get("field") or "DISTINCT user_id"),
                alias=alias_value,
                table_mapping=metric_def.table_mapping  # 添加表映射信息
            )]
        
        # 2) 回退到关键词映射（仅聚合，不附带硬编码过滤）
        detected_metric = self._detect_metric_from_question(question)
        if detected_metric:
            return [self._create_aggregation(detected_metric)]
        
        # 3) 无兜底：返回空，交由 plan 进入 clarify
        return []
    
    def parse_filters(self, state: Dict[str, Any]) -> List[SemanticFilter]:
        """
        解析度量相关的过滤器
        
        Args:
            state: 管道状态
            
        Returns:
            过滤器列表
        """
        question = str(state.get("question") or "").lower()
        
        # 若已解析到结构化度量，则直接返回注册表中的过滤器（通用，不仅限 MAU）
        metric_def = self._resolved_metric_def or self._resolve_metric_def(state)
        if metric_def and getattr(metric_def, "filters", None):
            out: List[SemanticFilter] = []
            for f in (metric_def.filters or []):
                try:
                    out.append(SemanticFilter(
                        field=str(f.get("field") or ""),
                        operator=str(f.get("operator") or "=").upper(),
                        value=str(f.get("value") or ""),
                    ))
                except Exception:
                    continue
            return out
        
        return []
    
    def _detect_metric_from_question(self, question: str) -> Optional[str]:
        """从问题文本中检测指标"""
        # 规则：
        # - 对纯字母数字关键字（如 mau/uv/pv/dau）使用“词边界/整词”匹配，避免 'maus' 命中 'mau'
        # - 对中文关键字（如 月活/活跃度）使用包含匹配
        import re as _re
        # 预先切分英文token
        tokens = [t for t in _re.split(r"[^a-z0-9]+", question) if t]
        token_set = set(tokens)
        for keyword, metric_alias in METRIC_KEYWORDS.items():
            kw = str(keyword).lower().strip()
            if not kw:
                continue
            if kw.isalnum():
                # 英文/数字：整词匹配
                if kw in token_set:
                    return metric_alias
            else:
                # 非英文：使用子串匹配
                if kw in question:
                    return metric_alias
        return None
    
    def _resolve_metric_def(self, state: Dict[str, Any]):
        """使用注册表解析度量定义，优先采用 clarified_inputs.metric，其次从原始问题中提取候选token精确匹配。"""
        try:
            from datainsight_agent.services.registry.metric_registry import MetricRegistry
            reg = MetricRegistry()
            clarified_metric = str((state.get("clarified_inputs") or {}).get("metric") or "").strip()
            if clarified_metric:
                got = reg.resolve_from_signals([clarified_metric])
                if got is not None:
                    return got
            # 回退：从原始问题中提取候选token/关键词后做精确匹配
            qtxt = str(state.get("question") or "").lower()
            if not qtxt:
                return None
            # 1) 关键词映射（如 mau/uv/pv/dau/中文别名）
            from datainsight_agent.config.keyword_mappings import METRIC_KEYWORDS
            candidates: list[str] = []
            # 先用已有的检测函数
            alias = self._detect_metric_from_question(qtxt)
            if alias:
                candidates.append(alias)
            # 2) 基于 token 的别名捕获（全英文数字的整词）
            import re as _re
            tokens = [t for t in _re.split(r"[^a-z0-9]+", qtxt) if t]
            candidates.extend(tokens)
            # 去重并按长度降序尝试
            seen = set()
            ordered = []
            for c in candidates:
                cc = str(c).strip().lower()
                if cc and cc not in seen:
                    seen.add(cc); ordered.append(cc)
            for c in ordered:
                got = reg.resolve_from_signals([c])
                if got is not None:
                    return got
            return None
        except Exception:
            return None
    
    def _create_aggregation(self, metric_alias: str) -> SemanticAggregation:
        """根据指标别名创建聚合函数"""
        if metric_alias in AGGREGATION_MAPPING:
            config = AGGREGATION_MAPPING[metric_alias]
            return SemanticAggregation(
                function=config["function"],
                field=config["field"],
                alias=metric_alias
            )
        else:
            # 默认使用COUNT
            return SemanticAggregation(
                function="COUNT",
                field="DISTINCT user_id",
                alias=metric_alias
            )
    
    # 无默认聚合函数：保留空，交由上游 plan 判定是否澄清


# 全局实例
_parser_instance = None

def parse_metrics(state: Dict[str, Any]) -> List[SemanticAggregation]:
    """解析度量的便捷函数"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = MetricParser()
    return _parser_instance.parse_metrics(state)

def parse_metric_filters(state: Dict[str, Any]) -> List[SemanticFilter]:
    """解析度量相关过滤器的便捷函数"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = MetricParser()
    return _parser_instance.parse_filters(state)
