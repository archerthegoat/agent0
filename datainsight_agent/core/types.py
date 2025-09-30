"""Core types used by decoupled components and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any


class TimeType(str, Enum):
    SINGLE = "single"
    RANGE = "range"
    QUARTER = "quarter"
    YEAR_RANGE = "year_range"
    RELATIVE = "relative"
    NONE = "none"


@dataclass
class TimeFilter:
    type: TimeType
    value: str
    confidence: float = 1.0


@dataclass
class QueryRewrite:
    rewritten_question: Optional[str]
    metric: List[str]
    group_by: List[str]
    time_filter: Optional[str]
    concepts: List[str]
    clarify: bool
    ask: Optional[str]
    # Optional semantic intent to guide downstream decisions
    query_intent: Optional["QueryIntent"] = None
    # RAG相关字段
    rag_context: Optional[str] = None
    rag_fragments: Optional[List[Dict[str, Any]]] = None


@dataclass
class QueryIntent:
    """High-level semantic intent extracted from the query.

    type: Overall task type.
    time_scope: The time scope detected.
    grouping_need: Whether grouping is needed and which style.
    business_context: Optional business semantics for downstream hints.
    """
    type: str  # "single_point" | "trend_analysis" | "range_comparison" | "aggregation_only"
    time_scope: str  # "single_month" | "month_range" | "quarter" | "year" | "relative" | "none"
    grouping_need: str  # "none" | "time_based" | "dimension_based"
    business_context: str = ""


@dataclass
class MetricInfo:
    key: str
    aliases: List[str]
    canonical_name: str


