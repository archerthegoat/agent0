from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SemanticFilter(BaseModel):
	field: str
	operator: str
	value: str
	# 新增：时间过滤的特殊字段
	time_type: Optional[str] = None  # "single", "range", "relative", "list"
	time_unit: Optional[str] = None   # "month", "day", "year", "week"


class SemanticAggregation(BaseModel):
	function: str
	field: Optional[str] = None
	alias: Optional[str] = None
	table_mapping: Optional[Dict[str, str]] = None  # 添加表映射信息


class SemanticJoin(BaseModel):
	right_table: str
	on: Dict[str, str]
	join_type: str = Field(default="inner")


class AttributionAnalysis(BaseModel):
	"""归因分析配置"""
	analysis_type: str = Field(default="trend")  # "trend", "attribution", "anomaly", "comparison"
	base_period: Optional[str] = None  # 基准期间，如 "2024-Q2"
	comparison_period: Optional[str] = None  # 对比期间，如 "2024-Q3"
	comparison_type: Optional[str] = None  # "quarter_over_quarter", "year_over_year", "month_over_month"
	threshold: Optional[float] = None  # 变化阈值，如 0.15 (15%)
	dimensions: List[str] = Field(default_factory=list)  # 分析维度
	metrics: List[str] = Field(default_factory=list)  # 分析指标


class SemanticQueryIR(BaseModel):
	"""Intermediate representation of a user's intent for SQL generation."""

	domain_entities: List[str] = Field(default_factory=list)
	target_metrics: List[str] = Field(default_factory=list)
	filters: List[SemanticFilter] = Field(default_factory=list)
	group_by: List[str] = Field(default_factory=list)
	aggregations: List[SemanticAggregation] = Field(default_factory=list)
	joins: List[SemanticJoin] = Field(default_factory=list)
	limit: Optional[int] = None
	order_by: Optional[List[str]] = None
	
	# 新增：归因分析支持
	attribution_analysis: Optional[AttributionAnalysis] = None
	report_type: Optional[str] = None  # "summary", "detailed", "attribution"
