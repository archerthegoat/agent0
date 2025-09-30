#!/usr/bin/env python3
"""
多维度评估指标定义
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import json
import time
from datetime import datetime


class MetricType(Enum):
    """指标类型枚举"""
    ACCURACY = "accuracy"  # 准确率
    PRECISION = "precision"  # 精确率
    RECALL = "recall"  # 召回率
    F1_SCORE = "f1_score"  # F1分数
    LATENCY = "latency"  # 延迟
    THROUGHPUT = "throughput"  # 吞吐量
    SUCCESS_RATE = "success_rate"  # 成功率
    ERROR_RATE = "error_rate"  # 错误率


class ComponentType(Enum):
    """组件类型枚举"""
    QUERY_REWRITER = "query_rewriter"  # 查询重写器
    IR_BUILDER = "ir_builder"  # IR构建器
    SQL_GENERATOR = "sql_generator"  # SQL生成器
    SQL_EXECUTOR = "sql_executor"  # SQL执行器
    RAG_SYSTEM = "rag_system"  # RAG系统
    METRIC_REGISTRY = "metric_registry"  # 指标注册表
    VECTOR_STORE = "vector_store"  # 向量存储
    LLM_SERVICE = "llm_service"  # LLM服务


@dataclass
class ComponentMetrics:
    """组件级评估指标"""
    component: ComponentType
    metrics: Dict[str, float] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    success_count: int = 0
    total_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.success_count / self.total_count if self.total_count > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """错误率"""
        return len(self.errors) / self.total_count if self.total_count > 0 else 0.0
    
    @property
    def avg_latency(self) -> float:
        """平均延迟"""
        if not self.timings:
            return 0.0
        return sum(self.timings.values()) / len(self.timings)


@dataclass
class RAGMetrics:
    """RAG系统评估指标"""
    # 基础指标
    recall_rate: Optional[float] = None  # 召回率
    precision_rate: Optional[float] = None  # 精确率
    f1_score: Optional[float] = None  # F1分数
    
    # 检索质量指标
    retrieved_fragments: int = 0  # 检索到的片段数
    relevant_fragments: int = 0  # 相关片段数
    total_relevant: int = 0  # 总相关片段数
    
    # 检索效率指标
    retrieval_latency: float = 0.0  # 检索延迟
    embedding_latency: float = 0.0  # 嵌入延迟
    search_latency: float = 0.0  # 搜索延迟
    
    # 上下文质量指标
    context_length: int = 0  # 上下文长度
    context_utilization: float = 0.0  # 上下文利用率
    context_relevance: float = 0.0  # 上下文相关性
    
    # 片段质量指标
    fragment_scores: List[float] = field(default_factory=list)  # 片段分数
    fragment_relevance: List[bool] = field(default_factory=list)  # 片段相关性
    
    def calculate_metrics(self):
        """计算RAG指标"""
        # 计算召回率
        if self.total_relevant > 0:
            self.recall_rate = self.relevant_fragments / self.total_relevant
        else:
            self.recall_rate = 0.0
        
        # 计算精确率
        if self.retrieved_fragments > 0:
            self.precision_rate = self.relevant_fragments / self.retrieved_fragments
        else:
            self.precision_rate = 0.0
        
        # 计算F1分数
        if self.recall_rate is not None and self.precision_rate is not None:
            if self.recall_rate + self.precision_rate > 0:
                self.f1_score = 2 * (self.recall_rate * self.precision_rate) / (self.recall_rate + self.precision_rate)
            else:
                self.f1_score = 0.0
        
        # 计算上下文利用率
        if self.context_length > 0:
            self.context_utilization = min(1.0, self.retrieved_fragments / self.context_length)
        
        # 计算上下文相关性
        if self.fragment_relevance:
            self.context_relevance = sum(self.fragment_relevance) / len(self.fragment_relevance)


@dataclass
class QueryMetrics:
    """单次查询评估指标"""
    query_id: str
    question: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 组件级指标
    query_rewriter: ComponentMetrics = field(default_factory=lambda: ComponentMetrics(ComponentType.QUERY_REWRITER))
    ir_builder: ComponentMetrics = field(default_factory=lambda: ComponentMetrics(ComponentType.IR_BUILDER))
    sql_generator: ComponentMetrics = field(default_factory=lambda: ComponentMetrics(ComponentType.SQL_GENERATOR))
    sql_executor: ComponentMetrics = field(default_factory=lambda: ComponentMetrics(ComponentType.SQL_EXECUTOR))
    
    # RAG指标
    rag_metrics: RAGMetrics = field(default_factory=RAGMetrics)
    
    # 整体指标
    total_latency: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    
    # 结果质量指标
    sql_correctness: bool = False
    result_completeness: bool = False
    result_accuracy: float = 0.0
    
    # 业务指标
    metric_identification_accuracy: float = 0.0
    time_parsing_accuracy: float = 0.0
    group_by_accuracy: float = 0.0
    
    def get_component_metrics(self, component: ComponentType) -> ComponentMetrics:
        """获取指定组件的指标"""
        component_map = {
            ComponentType.QUERY_REWRITER: self.query_rewriter,
            ComponentType.IR_BUILDER: self.ir_builder,
            ComponentType.SQL_GENERATOR: self.sql_generator,
            ComponentType.SQL_EXECUTOR: self.sql_executor,
        }
        return component_map.get(component, ComponentMetrics(component))


@dataclass
class BatchEvaluationMetrics:
    """批量评估指标"""
    evaluation_id: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # 查询级指标
    query_metrics: List[QueryMetrics] = field(default_factory=list)
    
    # 组件级汇总指标
    component_summary: Dict[ComponentType, ComponentMetrics] = field(default_factory=dict)
    
    # 整体指标
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    
    # 性能指标
    avg_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = float('inf')
    
    # 质量指标
    avg_sql_correctness: float = 0.0
    avg_result_completeness: float = 0.0
    avg_result_accuracy: float = 0.0
    avg_metric_identification_accuracy: float = 0.0
    avg_time_parsing_accuracy: float = 0.0
    avg_group_by_accuracy: float = 0.0
    
    # RAG汇总指标
    avg_rag_recall: float = 0.0
    avg_rag_precision: float = 0.0
    avg_rag_f1: float = 0.0
    avg_rag_latency: float = 0.0
    
    def calculate_summary_metrics(self):
        """计算汇总指标"""
        if not self.query_metrics:
            return
        
        self.total_queries = len(self.query_metrics)
        self.successful_queries = sum(1 for qm in self.query_metrics if qm.success)
        self.failed_queries = self.total_queries - self.successful_queries
        
        # 计算延迟指标
        latencies = [qm.total_latency for qm in self.query_metrics if qm.success]
        if latencies:
            self.avg_latency = sum(latencies) / len(latencies)
            self.max_latency = max(latencies)
            self.min_latency = min(latencies)
        
        # 计算质量指标
        self.avg_sql_correctness = sum(1 for qm in self.query_metrics if qm.sql_correctness) / self.total_queries
        self.avg_result_completeness = sum(1 for qm in self.query_metrics if qm.result_completeness) / self.total_queries
        self.avg_result_accuracy = sum(qm.result_accuracy for qm in self.query_metrics) / self.total_queries
        self.avg_metric_identification_accuracy = sum(qm.metric_identification_accuracy for qm in self.query_metrics) / self.total_queries
        self.avg_time_parsing_accuracy = sum(qm.time_parsing_accuracy for qm in self.query_metrics) / self.total_queries
        self.avg_group_by_accuracy = sum(qm.group_by_accuracy for qm in self.query_metrics) / self.total_queries
        
        # 计算RAG指标
        rag_metrics = [qm.rag_metrics for qm in self.query_metrics if qm.rag_metrics.recall_rate is not None]
        if rag_metrics:
            self.avg_rag_recall = sum(rm.recall_rate for rm in rag_metrics) / len(rag_metrics)
            self.avg_rag_precision = sum(rm.precision_rate for rm in rag_metrics) / len(rag_metrics)
            self.avg_rag_f1 = sum(rm.f1_score for rm in rag_metrics) / len(rag_metrics)
            self.avg_rag_latency = sum(rm.retrieval_latency for rm in rag_metrics) / len(rag_metrics)
        
        # 计算组件级汇总
        for component in ComponentType:
            component_metrics = [qm.get_component_metrics(component) for qm in self.query_metrics]
            if component_metrics:
                summary = ComponentMetrics(component)
                summary.total_count = sum(cm.total_count for cm in component_metrics)
                summary.success_count = sum(cm.success_count for cm in component_metrics)
                summary.errors = [error for cm in component_metrics for error in cm.errors]
                summary.timings = {f"query_{i}": cm.avg_latency for i, cm in enumerate(component_metrics) if cm.avg_latency > 0}
                self.component_summary[component] = summary
        
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "evaluation_id": self.evaluation_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "success_rate": self.successful_queries / self.total_queries if self.total_queries > 0 else 0.0,
            "performance": {
                "avg_latency": self.avg_latency,
                "max_latency": self.max_latency,
                "min_latency": self.min_latency,
            },
            "quality": {
                "sql_correctness": self.avg_sql_correctness,
                "result_completeness": self.avg_result_completeness,
                "result_accuracy": self.avg_result_accuracy,
                "metric_identification_accuracy": self.avg_metric_identification_accuracy,
                "time_parsing_accuracy": self.avg_time_parsing_accuracy,
                "group_by_accuracy": self.avg_group_by_accuracy,
            },
            "rag_metrics": {
                "recall": self.avg_rag_recall,
                "precision": self.avg_rag_precision,
                "f1_score": self.avg_rag_f1,
                "latency": self.avg_rag_latency,
            },
            "component_summary": {
                component.value: {
                    "success_rate": metrics.success_rate,
                    "error_rate": metrics.error_rate,
                    "avg_latency": metrics.avg_latency,
                    "total_count": metrics.total_count,
                    "success_count": metrics.success_count,
                    "error_count": len(metrics.errors),
                }
                for component, metrics in self.component_summary.items()
            }
        }


@dataclass
class EvaluationConfig:
    """评估配置"""
    # 基础配置
    enable_rag_metrics: bool = True
    enable_component_metrics: bool = True
    enable_performance_metrics: bool = True
    
    # RAG评估配置
    rag_evaluation_method: str = "manual"  # manual, automatic, hybrid
    relevance_threshold: float = 0.7  # 相关性阈值
    max_retrieved_fragments: int = 10  # 最大检索片段数
    
    # 性能评估配置
    latency_threshold: float = 10.0  # 延迟阈值（秒）
    timeout_threshold: float = 30.0  # 超时阈值（秒）
    
    # 质量评估配置
    sql_correctness_check: bool = True
    result_completeness_check: bool = True
    result_accuracy_check: bool = True
    
    # 输出配置
    save_detailed_metrics: bool = True
    output_format: str = "json"  # json, csv, html
    output_file: Optional[str] = None
