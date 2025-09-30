#!/usr/bin/env python3
"""
多维度评估器实现
"""

import time
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .metrics import (
    QueryMetrics, BatchEvaluationMetrics, ComponentMetrics, RAGMetrics,
    ComponentType, EvaluationConfig
)
from ..core.types import QueryRewrite
from ..models.ir import SemanticQueryIR
from ..services.core.sql_executor import SQLExecutor
from ..config.settings import load_settings

logger = logging.getLogger(__name__)


class ComponentEvaluator:
    """组件评估器"""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
    
    def evaluate_query_rewriter(self, question: str, rewrite_result: QueryRewrite, 
                              expected_metrics: List[str] = None, 
                              expected_time_filter: str = None,
                              expected_group_by: List[str] = None) -> ComponentMetrics:
        """评估查询重写器"""
        metrics = ComponentMetrics(ComponentType.QUERY_REWRITER)
        metrics.total_count = 1
        
        try:
            # 检查指标识别准确性
            if expected_metrics:
                identified_metrics = rewrite_result.metric or []
                correct_metrics = sum(1 for exp_metric in expected_metrics 
                                    if any(exp_metric.lower() in str(metric).lower() 
                                          for metric in identified_metrics))
                metrics.metrics["metric_identification_accuracy"] = correct_metrics / len(expected_metrics)
            else:
                metrics.metrics["metric_identification_accuracy"] = 1.0 if rewrite_result.metric else 0.0
            
            # 检查时间解析准确性
            if expected_time_filter:
                actual_time = str(rewrite_result.time_filter) if rewrite_result.time_filter else ""
                metrics.metrics["time_parsing_accuracy"] = 1.0 if expected_time_filter in actual_time else 0.0
            else:
                metrics.metrics["time_parsing_accuracy"] = 1.0 if rewrite_result.time_filter else 0.0
            
            # 检查分组准确性
            if expected_group_by:
                actual_group_by = rewrite_result.group_by or []
                correct_groups = sum(1 for exp_group in expected_group_by 
                                   if any(exp_group.lower() in str(group).lower() 
                                         for group in actual_group_by))
                metrics.metrics["group_by_accuracy"] = correct_groups / len(expected_group_by)
            else:
                metrics.metrics["group_by_accuracy"] = 1.0 if not rewrite_result.group_by else 0.0
            
            # 检查RAG上下文质量
            if rewrite_result.rag_context:
                metrics.metrics["rag_context_length"] = len(rewrite_result.rag_context)
                metrics.metrics["rag_fragments_count"] = len(rewrite_result.rag_fragments or [])
            
            metrics.success_count = 1
            
        except Exception as e:
            metrics.errors.append(str(e))
            logger.error(f"查询重写器评估失败: {e}")
        
        return metrics
    
    def evaluate_ir_builder(self, rewrite_result: QueryRewrite, ir_result: SemanticQueryIR) -> ComponentMetrics:
        """评估IR构建器"""
        metrics = ComponentMetrics(ComponentType.IR_BUILDER)
        metrics.total_count = 1
        
        try:
            # 检查IR构建完整性
            metrics.metrics["ir_completeness"] = 1.0 if ir_result.target_metrics else 0.0
            metrics.metrics["ir_metrics_count"] = len(ir_result.target_metrics or [])
            metrics.metrics["ir_filters_count"] = len(ir_result.filters or [])
            metrics.metrics["ir_group_by_count"] = len(ir_result.group_by or [])
            
            # 检查指标映射准确性
            if rewrite_result.metric and ir_result.target_metrics:
                mapped_metrics = sum(1 for metric in rewrite_result.metric 
                                   if any(metric.lower() in str(target).lower() 
                                         for target in ir_result.target_metrics))
                metrics.metrics["metric_mapping_accuracy"] = mapped_metrics / len(rewrite_result.metric)
            else:
                metrics.metrics["metric_mapping_accuracy"] = 0.0
            
            metrics.success_count = 1
            
        except Exception as e:
            metrics.errors.append(str(e))
            logger.error(f"IR构建器评估失败: {e}")
        
        return metrics
    
    def evaluate_sql_generator(self, ir_result: SemanticQueryIR, sql_result: str) -> ComponentMetrics:
        """评估SQL生成器"""
        metrics = ComponentMetrics(ComponentType.SQL_GENERATOR)
        metrics.total_count = 1
        
        try:
            # 检查SQL语法正确性
            metrics.metrics["sql_syntax_correctness"] = 1.0 if sql_result and sql_result.strip() else 0.0
            
            # 检查SQL完整性
            required_keywords = ["SELECT", "FROM"]
            found_keywords = sum(1 for keyword in required_keywords if keyword in sql_result.upper())
            metrics.metrics["sql_completeness"] = found_keywords / len(required_keywords)
            
            # 检查聚合函数使用
            if ir_result.target_metrics:
                has_aggregation = any(func in sql_result.upper() for func in ["COUNT", "SUM", "AVG", "MAX", "MIN"])
                metrics.metrics["aggregation_usage"] = 1.0 if has_aggregation else 0.0
            
            # 检查时间过滤
            if ir_result.filters:
                has_time_filter = any("month" in sql_result.lower() or "date" in sql_result.lower() 
                                    for filter_item in ir_result.filters)
                metrics.metrics["time_filter_usage"] = 1.0 if has_time_filter else 0.0
            
            # 检查分组
            if ir_result.group_by:
                has_group_by = "GROUP BY" in sql_result.upper()
                metrics.metrics["group_by_usage"] = 1.0 if has_group_by else 0.0
            
            metrics.success_count = 1
            
        except Exception as e:
            metrics.errors.append(str(e))
            logger.error(f"SQL生成器评估失败: {e}")
        
        return metrics
    
    def evaluate_sql_executor(self, sql_result: str, execution_result: List[Dict[str, Any]]) -> ComponentMetrics:
        """评估SQL执行器"""
        metrics = ComponentMetrics(ComponentType.SQL_EXECUTOR)
        metrics.total_count = 1
        
        try:
            # 检查执行成功率
            metrics.metrics["execution_success"] = 1.0 if execution_result is not None else 0.0
            
            # 检查结果完整性
            if execution_result:
                metrics.metrics["result_completeness"] = 1.0 if len(execution_result) > 0 else 0.0
                metrics.metrics["result_count"] = len(execution_result)
                
                # 检查结果格式
                if execution_result and isinstance(execution_result[0], dict):
                    metrics.metrics["result_format_correctness"] = 1.0
                else:
                    metrics.metrics["result_format_correctness"] = 0.0
            else:
                metrics.metrics["result_completeness"] = 0.0
                metrics.metrics["result_count"] = 0
                metrics.metrics["result_format_correctness"] = 0.0
            
            metrics.success_count = 1
            
        except Exception as e:
            metrics.errors.append(str(e))
            logger.error(f"SQL执行器评估失败: {e}")
        
        return metrics


class RAGEvaluator:
    """RAG评估器"""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
    
    def evaluate_rag_quality(self, question: str, rag_context: str, 
                           rag_fragments: List[Dict[str, Any]], 
                           expected_entities: List[str] = None) -> RAGMetrics:
        """评估RAG质量"""
        metrics = RAGMetrics()
        
        try:
            # 基础统计
            metrics.retrieved_fragments = len(rag_fragments or [])
            metrics.context_length = len(rag_context) if rag_context else 0
            
            # 计算相关性（基于预期实体）
            if expected_entities and rag_fragments:
                relevant_count = 0
                for fragment in rag_fragments:
                    fragment_text = str(fragment.get("content", ""))
                    if any(entity.lower() in fragment_text.lower() for entity in expected_entities):
                        relevant_count += 1
                        metrics.fragment_relevance.append(True)
                    else:
                        metrics.fragment_relevance.append(False)
                
                metrics.relevant_fragments = relevant_count
                metrics.total_relevant = len(expected_entities)  # 简化假设
            
            # 计算片段分数（基于相似度分数）
            if rag_fragments:
                scores = []
                for fragment in rag_fragments:
                    score = fragment.get("score", 0.0)
                    if isinstance(score, (int, float)):
                        scores.append(float(score))
                    else:
                        scores.append(0.0)
                metrics.fragment_scores = scores
            
            # 计算指标
            metrics.calculate_metrics()
            
        except Exception as e:
            logger.error(f"RAG质量评估失败: {e}")
        
        return metrics
    
    def evaluate_rag_performance(self, start_time: float, end_time: float, 
                               embedding_time: float = 0.0, 
                               search_time: float = 0.0) -> RAGMetrics:
        """评估RAG性能"""
        metrics = RAGMetrics()
        
        try:
            metrics.retrieval_latency = end_time - start_time
            metrics.embedding_latency = embedding_time
            metrics.search_latency = search_time
            
        except Exception as e:
            logger.error(f"RAG性能评估失败: {e}")
        
        return metrics


class ComprehensiveEvaluator:
    """综合评估器"""
    
    def __init__(self, config: EvaluationConfig = None):
        self.config = config or EvaluationConfig()
        self.component_evaluator = ComponentEvaluator(self.config)
        self.rag_evaluator = RAGEvaluator(self.config)
        self.settings = load_settings()
        self.sql_executor = SQLExecutor(self.settings)
    
    def evaluate_single_query(self, question: str, 
                            expected_metrics: List[str] = None,
                            expected_time_filter: str = None,
                            expected_group_by: List[str] = None,
                            expected_entities: List[str] = None) -> QueryMetrics:
        """评估单个查询"""
        query_id = str(uuid.uuid4())
        query_metrics = QueryMetrics(query_id=query_id, question=question)
        
        start_time = time.time()
        
        try:
            # 导入组件
            from ..components.query_rewriter.service import QueryRewriter
            from ..components.ir_builder.service import IRBuilder
            from ..services.core.sql_generator import SQLGenerator
            
            # 初始化组件
            query_rewriter = QueryRewriter()
            ir_builder = IRBuilder()
            sql_generator = SQLGenerator()
            
            # 1. 查询重写阶段
            rewrite_start = time.time()
            rewrite_result = query_rewriter.rewrite(question)
            rewrite_time = time.time() - rewrite_start
            
            query_metrics.query_rewriter = self.component_evaluator.evaluate_query_rewriter(
                question, rewrite_result, expected_metrics, expected_time_filter, expected_group_by
            )
            query_metrics.query_rewriter.timings["rewrite"] = rewrite_time
            
            # 2. IR构建阶段
            ir_start = time.time()
            ir_result = ir_builder.build(rewrite_result)
            ir_time = time.time() - ir_start
            
            query_metrics.ir_builder = self.component_evaluator.evaluate_ir_builder(rewrite_result, ir_result)
            query_metrics.ir_builder.timings["ir_build"] = ir_time
            
            # 3. SQL生成阶段
            sql_gen_start = time.time()
            sql_result = sql_generator.generate(ir_result)
            sql_gen_time = time.time() - sql_gen_start
            
            query_metrics.sql_generator = self.component_evaluator.evaluate_sql_generator(ir_result, sql_result)
            query_metrics.sql_generator.timings["sql_generation"] = sql_gen_time
            
            # 4. SQL执行阶段
            sql_exec_start = time.time()
            execution_result = self.sql_executor.execute(sql_result)
            sql_exec_time = time.time() - sql_exec_start
            
            query_metrics.sql_executor = self.component_evaluator.evaluate_sql_executor(sql_result, execution_result)
            query_metrics.sql_executor.timings["sql_execution"] = sql_exec_time
            
            # 5. RAG评估
            if self.config.enable_rag_metrics and rewrite_result.rag_context:
                rag_metrics = self.rag_evaluator.evaluate_rag_quality(
                    question, rewrite_result.rag_context, rewrite_result.rag_fragments, expected_entities
                )
                query_metrics.rag_metrics = rag_metrics
            
            # 6. 整体评估
            query_metrics.total_latency = time.time() - start_time
            query_metrics.success = True
            
            # 计算整体质量指标
            query_metrics.sql_correctness = query_metrics.sql_generator.metrics.get("sql_syntax_correctness", 0.0) > 0.5
            query_metrics.result_completeness = query_metrics.sql_executor.metrics.get("result_completeness", 0.0) > 0.5
            query_metrics.result_accuracy = 1.0 if execution_result else 0.0
            
            query_metrics.metric_identification_accuracy = query_metrics.query_rewriter.metrics.get("metric_identification_accuracy", 0.0)
            query_metrics.time_parsing_accuracy = query_metrics.query_rewriter.metrics.get("time_parsing_accuracy", 0.0)
            query_metrics.group_by_accuracy = query_metrics.query_rewriter.metrics.get("group_by_accuracy", 0.0)
            
        except Exception as e:
            query_metrics.success = False
            query_metrics.error_message = str(e)
            query_metrics.total_latency = time.time() - start_time
            logger.error(f"查询评估失败: {e}")
        
        return query_metrics
    
    def evaluate_batch_queries(self, test_cases: List[Dict[str, Any]]) -> BatchEvaluationMetrics:
        """批量评估查询"""
        evaluation_id = str(uuid.uuid4())
        batch_metrics = BatchEvaluationMetrics(evaluation_id=evaluation_id)
        
        logger.info(f"开始批量评估，共 {len(test_cases)} 个测试用例")
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"评估测试用例 {i+1}/{len(test_cases)}: {test_case.get('question', 'Unknown')}")
            
            query_metrics = self.evaluate_single_query(
                question=test_case.get("question", ""),
                expected_metrics=test_case.get("expected_metrics"),
                expected_time_filter=test_case.get("expected_time_filter"),
                expected_group_by=test_case.get("expected_group_by"),
                expected_entities=test_case.get("expected_entities")
            )
            
            batch_metrics.query_metrics.append(query_metrics)
        
        # 计算汇总指标
        batch_metrics.calculate_summary_metrics()
        
        logger.info(f"批量评估完成，成功率: {batch_metrics.successful_queries}/{batch_metrics.total_queries}")
        
        return batch_metrics
    
    def save_evaluation_results(self, batch_metrics: BatchEvaluationMetrics, 
                              output_file: str = None) -> str:
        """保存评估结果"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"evaluation_results_{timestamp}.json"
        
        results_dict = batch_metrics.to_dict()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评估结果已保存到: {output_file}")
        return output_file
    
    def print_evaluation_summary(self, batch_metrics: BatchEvaluationMetrics):
        """打印评估摘要"""
        print("\n" + "="*80)
        print("📊 多维度评估结果摘要")
        print("="*80)
        
        # 整体统计
        print(f"总查询数: {batch_metrics.total_queries}")
        print(f"成功查询: {batch_metrics.successful_queries}")
        print(f"失败查询: {batch_metrics.failed_queries}")
        print(f"成功率: {batch_metrics.successful_queries/batch_metrics.total_queries*100:.1f}%")
        
        # 性能指标
        print(f"\n⚡ 性能指标:")
        print(f"平均延迟: {batch_metrics.avg_latency:.2f}s")
        print(f"最大延迟: {batch_metrics.max_latency:.2f}s")
        print(f"最小延迟: {batch_metrics.min_latency:.2f}s")
        
        # 质量指标
        print(f"\n🎯 质量指标:")
        print(f"SQL正确率: {batch_metrics.avg_sql_correctness*100:.1f}%")
        print(f"结果完整性: {batch_metrics.avg_result_completeness*100:.1f}%")
        print(f"结果准确性: {batch_metrics.avg_result_accuracy*100:.1f}%")
        print(f"指标识别准确率: {batch_metrics.avg_metric_identification_accuracy*100:.1f}%")
        print(f"时间解析准确率: {batch_metrics.avg_time_parsing_accuracy*100:.1f}%")
        print(f"分组准确率: {batch_metrics.avg_group_by_accuracy*100:.1f}%")
        
        # RAG指标
        if batch_metrics.avg_rag_recall > 0:
            print(f"\n🔍 RAG指标:")
            print(f"召回率: {batch_metrics.avg_rag_recall*100:.1f}%")
            print(f"精确率: {batch_metrics.avg_rag_precision*100:.1f}%")
            print(f"F1分数: {batch_metrics.avg_rag_f1*100:.1f}%")
            print(f"RAG延迟: {batch_metrics.avg_rag_latency:.2f}s")
        
        # 组件指标
        print(f"\n🔧 组件指标:")
        for component, metrics in batch_metrics.component_summary.items():
            print(f"{component.value}: 成功率 {metrics.success_rate*100:.1f}%, "
                  f"平均延迟 {metrics.avg_latency:.2f}s, "
                  f"错误数 {len(metrics.errors)}")
        
        print("="*80)
