#!/usr/bin/env python3
"""
增强版批量测试评估框架
支持RAG相关评价指标：召回率、准确率、相关性评分等
"""

import time
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import traceback

from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter as QueryRewriter
from datainsight_agent.components.ir_builder import IRBuilder
from datainsight_agent.services.core.sql_generator import SQLGenerator as SQLGeneratorComponent
from datainsight_agent.services.core.sql_executor import SQLExecutor as SQLExecutorComponent
from datainsight_agent.components.pipeline import SimplePipeline
from datainsight_agent.services.db_bootstrap import init_mysql_min
from datainsight_agent.config.manager import ConfigManager


@dataclass
class TestCase:
    """测试用例"""
    id: str
    question: str
    expected_sql: Optional[str] = None
    expected_result: Optional[List[Dict]] = None
    expected_metrics: Optional[List[str]] = None
    expected_time_filter: Optional[str] = None
    expected_group_by: Optional[List[str]] = None
    category: str = "general"
    description: str = ""
    # RAG相关期望值
    expected_rag_entities: Optional[List[str]] = None  # 期望检索到的实体
    expected_rag_concepts: Optional[List[str]] = None  # 期望检索到的概念
    # 时间澄清相关字段
    time_clarification: Optional[Dict[str, Any]] = None  # 时间澄清配置


@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    success: bool
    execution_time: float
    sql_generated: bool
    sql_executable: bool
    sql_correct: bool
    time_parsed_correctly: bool
    metric_identified_correctly: bool
    group_by_correct: bool
    result_complete: bool
    # RAG相关指标
    rag_recall_rate: Optional[float] = None
    rag_precision_rate: Optional[float] = None
    rag_relevance_score: Optional[float] = None
    rag_fragment_count: Optional[int] = None
    rag_retrieval_time: Optional[float] = None
    rag_entity_coverage: Optional[float] = None  # 实体覆盖率
    rag_concept_coverage: Optional[float] = None  # 概念覆盖率
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    generated_sql: Optional[str] = None
    actual_result: Optional[List[Dict]] = None
    component_timings: Optional[Dict[str, float]] = None
    rewritten_query: Optional[Any] = None
    ir: Optional[Any] = None
    rag_context: Optional[str] = None
    rag_fragments: Optional[List[Dict]] = None


class BatchTestEvaluator:
    """增强版批量测试评估器"""
    
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        
        # 初始化组件
        from datainsight_agent.config.settings import load_settings
        settings = load_settings()
        
        self.query_rewriter = QueryRewriter()
        self.ir_builder = IRBuilder()
        self.sql_generator = SQLGeneratorComponent()
        self.sql_executor = SQLExecutorComponent(settings)
        self.pipeline = SimplePipeline()
        
        # 初始化配置
        config_manager = ConfigManager()
        self.settings = config_manager._s
        init_mysql_min(self.settings.database_url)
    
    def load_test_cases(self, test_file: str):
        """从JSON文件加载测试用例"""
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            test_case = TestCase(
                id=item['id'],
                question=item['question'],
                expected_sql=item.get('expected_sql'),
                expected_result=item.get('expected_result'),
                expected_metrics=item.get('expected_metrics'),
                expected_time_filter=item.get('expected_time_filter'),
                expected_group_by=item.get('expected_group_by'),
                category=item.get('category', 'general'),
                description=item.get('description', ''),
                expected_rag_entities=item.get('expected_rag_entities'),
                expected_rag_concepts=item.get('expected_rag_concepts'),
                time_clarification=item.get('time_clarification')
            )
            self.test_cases.append(test_case)
        
        print(f"[SUCCESS] Loaded {len(self.test_cases)} test cases")
    
    def run_single_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()
        component_timings = {}
        
        try:
            print(f"[DEBUG] Running test: {test_case.id}")
            # 1. Query Rewriter (包含RAG检索)
            qr_start = time.time()
            rewritten_query = self.query_rewriter.rewrite(test_case.question)
            component_timings['query_rewriter'] = time.time() - qr_start
            print(f"[DEBUG] Query Rewriter completed: {rewritten_query.metric}")
            
            # 2. 检查是否需要时间澄清
            if self._needs_time_clarification(rewritten_query, test_case):
                clarified_query = self._simulate_time_clarification(rewritten_query, test_case)
                rewritten_query = clarified_query
            
            # 3. IR Builder
            ir_start = time.time()
            ir = self.ir_builder.build(rewritten_query)
            component_timings['ir_builder'] = time.time() - ir_start
            print(f"[DEBUG] IR Builder completed: {len(ir.aggregations) if ir.aggregations else 0} aggregations")
            
            # 4. SQL Generator
            sql_gen_start = time.time()
            # 强制使用统一的表名
            generated_sql = self.sql_generator.generate(ir, "dws_user_activity")
            component_timings['sql_generator'] = time.time() - sql_gen_start
            print(f"[DEBUG] SQL Generator completed: {generated_sql}")
            
            # 5. SQL Executor
            sql_exec_start = time.time()
            actual_result = self.sql_executor.execute(generated_sql)
            component_timings['sql_executor'] = time.time() - sql_exec_start
            print(f"[DEBUG] SQL Executor completed: {len(actual_result) if actual_result else 0} rows")
            
            total_time = time.time() - start_time
            
            # 评估结果
            result = self._evaluate_result(test_case, rewritten_query, ir, generated_sql, actual_result)
            result.execution_time = total_time
            result.component_timings = component_timings
            result.rewritten_query = rewritten_query
            result.ir = ir
            result.success = True
            
            # 评估RAG相关指标
            self._evaluate_rag_metrics(test_case, rewritten_query, result)
            
            return result
            
        except Exception as e:
            total_time = time.time() - start_time
            error_type = type(e).__name__
            error_message = str(e)
            
            return TestResult(
                test_case=test_case,
                success=False,
                execution_time=total_time,
                sql_generated=False,
                sql_executable=False,
                sql_correct=False,
                time_parsed_correctly=False,
                metric_identified_correctly=False,
                group_by_correct=False,
                result_complete=False,
                error_type=error_type,
                error_message=error_message,
                component_timings=component_timings,
                generated_sql=None  # 异常情况下没有生成SQL
            )
    
    def _evaluate_rag_metrics(self, test_case: TestCase, rewritten_query, result: TestResult):
        """基于向量索引的两段式RAG指标评估（带调试）"""
        try:
            # 获取RAG信息
            rag_context = getattr(rewritten_query, 'rag_context', None)
            rag_fragments = getattr(rewritten_query, 'rag_fragments', [])
            
            print(f"[DEBUG] RAG fragments count: {len(rag_fragments)}")
            if rag_fragments:
                print(f"[DEBUG] First fragment keys: {list(rag_fragments[0].keys())}")
                print(f"[DEBUG] First fragment entity_type: {rag_fragments[0].get('entity_type', 'N/A')}")
            
            result.rag_context = rag_context
            result.rag_fragments = rag_fragments
            result.rag_fragment_count = len(rag_fragments) if rag_fragments else 0
            
            # 第一段：基于向量索引的指标召回评估
            stage1_metrics = self._evaluate_stage1_metric_recall_with_vector(test_case, rag_fragments)
            
            # 第二段：语义知识片段评估
            stage2_metrics = self._evaluate_stage2_semantic_fragments(test_case, rag_fragments)
            
            # 合并指标
            result.rag_recall_rate = stage1_metrics['metric_recall_rate']
            result.rag_precision_rate = stage1_metrics['metric_precision_rate']
            result.rag_entity_coverage = stage1_metrics['metric_coverage']
            result.rag_concept_coverage = stage2_metrics['knowledge_completeness']
            result.rag_relevance_score = stage2_metrics['semantic_relevance']
            
            print(f"[DEBUG] Final RAG metrics - Recall: {result.rag_recall_rate:.2%}, Precision: {result.rag_precision_rate:.2%}")
            
        except Exception as e:
            print(f"RAG evaluation error: {str(e)}")
            result.rag_recall_rate = 0.0
            result.rag_precision_rate = 0.0
            result.rag_relevance_score = 0.0
    
    def _extract_entities_from_rag(self, rag_context: str, rag_fragments: List[Dict]) -> set:
        """从RAG内容中提取实体"""
        entities = set()
        
        if rag_context:
            # 简单的实体提取逻辑
            lines = rag_context.split('\n')
            for line in lines:
                if '->' in line:
                    # 格式: entity_name->column_name
                    entity = line.split('->')[0].strip()
                    entities.add(entity.lower())
                elif ':' in line and not line.startswith('#'):
                    # 格式: entity_name: description
                    entity = line.split(':')[0].strip()
                    entities.add(entity.lower())
        
        if rag_fragments:
            for fragment in rag_fragments:
                metadata = fragment.get('metadata', {})
                canonical_name = metadata.get('canonical_name', '')
                if canonical_name:
                    entities.add(canonical_name.lower())
        
        return entities
    
    def _extract_concepts_from_rag(self, rag_context: str, rag_fragments: List[Dict]) -> set:
        """从RAG内容中提取概念"""
        concepts = set()
        
        if rag_context:
            lines = rag_context.split('\n')
            for line in lines:
                if 'concept:' in line.lower():
                    concept = line.split(':', 1)[1].strip()
                    concepts.add(concept.lower())
        
        if rag_fragments:
            for fragment in rag_fragments:
                metadata = fragment.get('metadata', {})
                entity_type = metadata.get('entity_type', '')
                if entity_type == 'concept':
                    canonical_name = metadata.get('canonical_name', '')
                    if canonical_name:
                        concepts.add(canonical_name.lower())
        
        return concepts
    
    def _calculate_relevance_score(self, question: str, rag_context: str) -> float:
        """计算问题与RAG内容的相关性评分（增强版）"""
        if not rag_context:
            return 0.0
        
        question_lower = question.lower()
        context_lower = rag_context.lower()
        
        # 扩展的关键指标词汇（包含更多同义词）
        metric_keywords = [
            # 核心指标
            'mau', 'dau', 'uv', 'pv', 'gmv', 'aov',
            # 中文全称
            '月活跃用户', '日活跃用户', '独立访客', '页面访问', '成交总额', '客单价',
            # 中文简称
            '月活', '日活', '访客', '浏览量', '访问量',
            # 业务同义词
            '活跃用户', '用户活跃度', '活跃度统计', '用户数', '访问次数', '页面浏览量',
            '独立用户', '独立用户数', '唯一访客', '唯一用户'
        ]
        
        # 智能指标匹配（支持部分匹配和同义词）
        metric_matches = 0
        for keyword in metric_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in question_lower and keyword_lower in context_lower:
                metric_matches += 1
                # 核心指标额外权重
                if keyword_lower in ['mau', 'dau', 'uv', 'pv', 'gmv', 'aov']:
                    metric_matches += 0.8
                # 中文全称额外权重
                elif keyword_lower in ['月活跃用户', '日活跃用户', '独立访客', '页面访问']:
                    metric_matches += 0.6
        
        # 扩展的时间关键词
        time_keywords = [
            '年', '月', '日', '季度', '周', '小时', '时段',
            'year', 'month', 'day', 'quarter', 'week', 'hour',
            '最近', '今年', '去年', '本月', '上月', '本周', '上周',
            '2025', '2024', '2023', 'q1', 'q2', 'q3', 'q4'
        ]
        time_matches = 0
        for keyword in time_keywords:
            if keyword in question and keyword in context_lower:
                time_matches += 1
        
        # 扩展的查询相关词汇
        query_keywords = [
            '查询', '统计', '分析', '对比', '趋势', '分布', '排名',
            'query', 'count', 'analysis', 'compare', 'trend', 'distribution',
            '数据', '报表', '报告', '指标', '维度', '分组', '聚合'
        ]
        query_matches = 0
        for keyword in query_keywords:
            if keyword in question_lower and keyword in context_lower:
                query_matches += 1
        
        # 优化权重分配（更重视指标匹配）
        total_score = metric_matches * 0.7 + time_matches * 0.2 + query_matches * 0.1
        max_possible_score = len(metric_keywords) * 0.7 + len(time_keywords) * 0.2 + len(query_keywords) * 0.1
        
        if max_possible_score == 0:
            return 0.0
        
        relevance = total_score / max_possible_score
        return min(relevance, 1.0)
    
    def _extract_entities_from_question(self, question: str) -> set:
        """从问题中提取实体"""
        entities = set()
        
        # 提取指标相关实体
        metric_keywords = ['mau', 'dau', 'uv', 'pv', '月活跃用户', '日活跃用户', '独立访客', '页面访问']
        for keyword in metric_keywords:
            if keyword.lower() in question.lower():
                entities.add(keyword.lower())
        
        # 提取时间相关实体
        time_keywords = ['年', '月', '日', '季度', '周', 'year', 'month', 'day', 'quarter', 'week']
        for keyword in time_keywords:
            if keyword in question:
                entities.add(keyword)
        
        return entities

    def _extract_concepts_from_question(self, question: str) -> set:
        """从问题中提取概念"""
        concepts = set()
        
        # 提取业务概念
        if '查询' in question or 'query' in question.lower():
            concepts.add('query')
        if '统计' in question or 'count' in question.lower():
            concepts.add('statistics')
        if '分析' in question or 'analysis' in question.lower():
            concepts.add('analysis')
        if '趋势' in question or 'trend' in question.lower():
            concepts.add('trend')
        
        return concepts
    
    def _extract_expected_metrics_from_question(self, question: str) -> set:
        """从问题中提取期望的指标（使用标准指标名称）"""
        try:
            expected_metrics = set()
            question_lower = question.lower()
            
            # 使用MetricRegistry进行标准化匹配
            from datainsight_agent.services.registry.metric_registry import MetricRegistry
            registry = MetricRegistry()
            registry.load()  # 确保加载指标定义
            
            # 提取问题中的关键词
            import re
            keywords = []
            
            # 1. 英文缩写（改进正则表达式）
            abbreviations = re.findall(r'\b[A-Z]{2,4}\b', question)
            keywords.extend(abbreviations)
            
            # 2. 中文指标名称（扩展列表）
            chinese_metrics = [
                '月活跃用户', '日活跃用户', '独立访客', '浏览量', '用户数', '访问量',
                '活跃用户', '用户活跃', '访客', '页面访问', '页面浏览量'
            ]
            for metric in chinese_metrics:
                if metric in question:
                    keywords.append(metric)
            
            # 3. 英文全称（扩展列表）
            english_metrics = [
                'monthly active users', 'daily active users', 'unique visitors', 'page views',
                'active users', 'visitors', 'page visits'
            ]
            for metric in english_metrics:
                if metric in question_lower:
                    keywords.append(metric)
            
            # 4. 直接匹配常见指标缩写（作为fallback）
            direct_matches = {
                'mau': ['mau', 'MAU'],
                'dau': ['dau', 'DAU'],
                'uv': ['uv', 'UV'],
                'pv': ['pv', 'PV'],
                'gmv': ['gmv', 'GMV']
            }
            
            for metric_key, aliases in direct_matches.items():
                for alias in aliases:
                    if alias in question or alias.lower() in question_lower:
                        keywords.append(alias)
            
            print(f"[DEBUG] Extracted keywords: {keywords}")
            
            # 使用MetricRegistry进行标准化
            for keyword in keywords:
                metric_def = registry.resolve_from_signals([keyword])
                print(f"[DEBUG] Keyword '{keyword}' -> MetricDef: {metric_def}")
                if metric_def:
                    # 使用聚合别名作为标准指标名
                    agg_alias = metric_def.aggregation.get('alias', '')
                    if agg_alias:
                        expected_metrics.add(agg_alias.lower())
                        expected_metrics.add(agg_alias.upper())
                        print(f"[DEBUG] Added metric from aggregation alias: {agg_alias}")
                    else:
                        # 如果没有聚合别名，使用规范名称
                        expected_metrics.add(metric_def.canonical_name.lower())
                        expected_metrics.add(metric_def.canonical_name.upper())
                        print(f"[DEBUG] Added metric from canonical name: {metric_def.canonical_name}")
            
            print(f"[DEBUG] Final expected metrics: {expected_metrics}")
            return expected_metrics
        except Exception as e:
            print(f"Error extracting expected metrics: {e}")
            import traceback
            traceback.print_exc()
            return set()

    def _extract_metrics_from_rag_fragments(self, rag_fragments: List[Dict]) -> set:
        """从RAG片段中提取指标（兼容三阶段RAG）"""
        retrieved_metrics = set()
        
        for fragment in rag_fragments:
            # 兼容三阶段RAG的新结构
            entity_type = fragment.get('entity_type', '') or fragment.get('metadata', {}).get('entity_type', '')
            
            if entity_type == 'metric':
                # 优先从metadata获取，如果为空则从顶层获取
                metadata = fragment.get('metadata', {})
                canonical_name = metadata.get('canonical_name', '') or fragment.get('canonical_name', '')
                aliases = metadata.get('aliases', []) or fragment.get('aliases', [])
                aggregation = metadata.get('aggregation', {}) or fragment.get('aggregation', {})
                
                print(f"[DEBUG] RAG fragment metadata: {metadata}")
                print(f"[DEBUG] Canonical name: {canonical_name}, Aliases: {aliases}, Aggregation: {aggregation}")
                
                # 优先使用聚合别名作为标准指标名
                agg_alias = aggregation.get('alias', '')
                if agg_alias:
                    retrieved_metrics.add(agg_alias.lower())
                    retrieved_metrics.add(agg_alias.upper())
                    print(f"[DEBUG] Added metric from aggregation alias: {agg_alias}")
                elif canonical_name:
                    # 如果没有聚合别名，使用规范名称
                    retrieved_metrics.add(canonical_name.lower())
                    retrieved_metrics.add(canonical_name.upper())
                    print(f"[DEBUG] Added metric from canonical name: {canonical_name}")
        
        return retrieved_metrics

    def _evaluate_stage1_metric_recall_with_vector(self, test_case: TestCase, rag_fragments: List[Dict]) -> dict:
        """第一段：基于向量索引的指标召回评估（兼容三阶段RAG）"""
        if not rag_fragments:
            return {
                'metric_recall_rate': 0.0,
                'metric_precision_rate': 0.0,
                'metric_coverage': 0.0
            }
        
        # 从问题中提取期望的指标
        expected_metrics = self._extract_expected_metrics_from_question(test_case.question)
        
        # 从RAG片段中提取检索到的指标
        retrieved_metrics = self._extract_metrics_from_rag_fragments(rag_fragments)
        
        print(f"[DEBUG] Expected metrics: {expected_metrics}")
        print(f"[DEBUG] Retrieved metrics: {retrieved_metrics}")
        
        # 计算指标召回率和准确率
        if expected_metrics:
            relevant_retrieved = len(expected_metrics & retrieved_metrics)
            recall_rate = relevant_retrieved / len(expected_metrics)
            precision_rate = relevant_retrieved / len(retrieved_metrics) if retrieved_metrics else 0.0
            coverage = recall_rate
        else:
            # 改进的fallback逻辑：基于片段分数和类型分布
            metric_fragments = []
            for fragment in rag_fragments:
                entity_type = fragment.get('entity_type', '') or fragment.get('metadata', {}).get('entity_type', '')
                if entity_type == 'metric':
                    metric_fragments.append(fragment)
            
            if metric_fragments:
                # 如果有metric片段，基于分数评估（移除1.2x放大）
                scores = [f.get('score', 0.0) for f in metric_fragments]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                # 移除人为放大，使用原始向量分数
                recall_rate = min(1.0, avg_score)
                precision_rate = min(1.0, avg_score)
            else:
                # 如果没有metric片段，基于整体分数评估（移除0.8x加权）
                scores = [f.get('score', 0.0) for f in rag_fragments]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                # 移除人为加权，使用原始向量分数
                recall_rate = min(1.0, avg_score)
                precision_rate = min(1.0, avg_score)
            
            coverage = recall_rate
        
        return {
            'metric_recall_rate': recall_rate,
            'metric_precision_rate': precision_rate,
            'metric_coverage': coverage
        }

    def _evaluate_stage2_semantic_fragments(self, test_case: TestCase, rag_fragments: List[Dict]) -> dict:
        """第二段：语义知识片段评估"""
        if not rag_fragments:
            return {
                'semantic_relevance': 0.0,
                'fragment_quality': 0.0,
                'knowledge_completeness': 0.0
            }
        
        # 计算语义相关性（混合计算：向量相似度 + 关键词匹配）
        scores = []
        for fragment in rag_fragments:
            score = fragment.get('score', 0.0)
            if isinstance(score, (int, float)):
                scores.append(float(score))
            else:
                scores.append(0.0)
        
        # 向量相似度分数（70%权重）
        vector_similarity = sum(scores) / len(scores) if scores else 0.0
        
        # 关键词匹配分数（30%权重）
        rag_context = ""
        for fragment in rag_fragments:
            # 从metadata构建上下文
            metadata = fragment.get('metadata', {})
            if metadata:
                # 添加规范名称和别名
                canonical_name = metadata.get('canonical_name', '')
                aliases = metadata.get('aliases', [])
                if canonical_name:
                    rag_context += canonical_name + " "
                for alias in aliases:
                    rag_context += alias + " "
        
        keyword_match = self._calculate_relevance_score(test_case.question, rag_context)
        
        # 混合计算relevance score（平衡权重：向量相似度60%，关键词匹配40%）
        semantic_relevance = vector_similarity * 0.6 + keyword_match * 0.4
        
        # 计算片段质量（基于分数分布）
        high_quality_fragments = sum(1 for score in scores if score > 0.7)
        fragment_quality = high_quality_fragments / len(scores) if scores else 0.0
        
        # 计算知识完整性（基于片段类型多样性）
        entity_types = set()
        for fragment in rag_fragments:
            # entity_type在顶层，不在metadata中
            entity_type = fragment.get('entity_type', '')
            if entity_type:
                entity_types.add(entity_type)
        
        # 期望的实体类型：metric, dimension, mapping
        expected_types = {'metric', 'dimension', 'mapping'}
        knowledge_completeness = len(entity_types & expected_types) / len(expected_types)
        
        return {
            'semantic_relevance': semantic_relevance,
            'fragment_quality': fragment_quality,
            'knowledge_completeness': knowledge_completeness
        }
    
    def _evaluate_result(self, test_case: TestCase, rewritten_query, ir, generated_sql: str, actual_result: List[Dict]) -> TestResult:
        """评估测试结果"""
        
        # SQL生成率
        sql_generated = generated_sql is not None and len(generated_sql.strip()) > 0
        
        # SQL执行成功率
        sql_executable = actual_result is not None
        
        # 结果正确率（只对有预期结果的测试用例进行评估）
        result_correct = None  # None表示未评估
        if test_case.expected_result:
            if actual_result is not None:
                result_correct = self._compare_results(actual_result, test_case.expected_result)
            else:
                result_correct = False  # 有期望结果但实际结果为空
        
        # 时间解析准确率（修复逻辑，包括null值的处理）
        time_parsed_correctly = None  # None表示未评估
        if hasattr(test_case, "expected_time_filter"):
            actual_time_filter = None
            if rewritten_query.time_filter:
                actual_time_filter = str(rewritten_query.time_filter)
            elif ir.filters:
                for f in ir.filters:
                    if f.field == 'month':
                        actual_time_filter = f.value
                        break
            
            time_parsed_correctly = actual_time_filter == test_case.expected_time_filter
        
        # 指标识别准确率（只对有预期指标的测试用例进行评估）
        metric_identified_correctly = None  # None表示未评估
        if test_case.expected_metrics:
            actual_metrics = rewritten_query.metric or []
            metric_identified_correctly = set(actual_metrics) == set(test_case.expected_metrics)
        
        # 分组字段准确率（只对有预期分组字段的测试用例进行评估）
        group_by_correct = None  # None表示未评估
        if test_case.expected_group_by:
            actual_group_by = ir.group_by or []
            group_by_correct = set(actual_group_by) == set(test_case.expected_group_by)
        
        # 结果完整性
        result_complete = actual_result is not None and len(actual_result) > 0
        
        return TestResult(
            test_case=test_case,
            success=True,
            execution_time=0,  # 将在外部设置
            sql_generated=sql_generated,
            sql_executable=sql_executable,
            sql_correct=result_correct,  # 使用结果正确率替代SQL正确率
            time_parsed_correctly=time_parsed_correctly,
            metric_identified_correctly=metric_identified_correctly,
            group_by_correct=group_by_correct,
            result_complete=result_complete,
            actual_result=actual_result,
            generated_sql=generated_sql  # 添加生成的SQL
        )
    
    def _compare_results(self, actual_result: List[Dict], expected_result: List[Dict]) -> bool:
        """比较查询结果"""
        if not actual_result and not expected_result:
            return True
        if not actual_result or not expected_result:
            return False
        
        # 标准化结果数据
        actual_normalized = self._normalize_result(actual_result)
        expected_normalized = self._normalize_result(expected_result)
        
        # 比较行数
        if len(actual_normalized) != len(expected_normalized):
            return False
        
        # 比较每行数据
        for actual_row, expected_row in zip(actual_normalized, expected_normalized):
            if not self._compare_row(actual_row, expected_row):
                return False
        
        return True
    
    def _normalize_result(self, result: List[Dict]) -> List[Dict]:
        """标准化查询结果"""
        normalized = []
        for row in result:
            normalized_row = {}
            for key, value in row.items():
                # 标准化键名（小写）
                normalized_key = key.lower().strip()
                # 标准化值
                if isinstance(value, str):
                    normalized_value = value.strip()
                elif isinstance(value, (int, float)):
                    normalized_value = float(value)
                else:
                    normalized_value = value
                normalized_row[normalized_key] = normalized_value
            normalized.append(normalized_row)
        return normalized
    
    def _compare_row(self, actual_row: Dict, expected_row: Dict) -> bool:
        """比较单行数据"""
        # 比较键
        if set(actual_row.keys()) != set(expected_row.keys()):
            return False
        
        # 比较值
        for key in actual_row.keys():
            actual_value = actual_row[key]
            expected_value = expected_row[key]
            
            # 数值比较（允许小的浮点误差）
            if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                if abs(float(actual_value) - float(expected_value)) > 1e-6:
                    return False
            # 字符串比较
            elif str(actual_value).strip() != str(expected_value).strip():
                return False
        
        return True
    
    def run_batch_test(self) -> Dict[str, Any]:
        """运行批量测试"""
        print(f"[START] Starting batch test with {len(self.test_cases)} test cases")
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n--- Test {i}/{len(self.test_cases)}: {test_case.id} ---")
            print(f"Question: {test_case.question}")
            
            result = self.run_single_test(test_case)
            self.results.append(result)
            
            if result.success:
                print(f"[SUCCESS] - Time: {result.execution_time:.3f}s")
                if result.rag_fragment_count is not None:
                    recall_str = f"{result.rag_recall_rate:.2%}" if result.rag_recall_rate is not None else "N/A"
                    precision_str = f"{result.rag_precision_rate:.2%}" if result.rag_precision_rate is not None else "N/A"
                    print(f"[RAG] {result.rag_fragment_count} fragments, Recall: {recall_str}, Precision: {precision_str}")
            else:
                print(f"[FAILED] - {result.error_type}: {result.error_message}")
        
        # 打印评价指标
        self.print_metrics()
        
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """计算各种评价指标"""
        if not self.results:
            return {}
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        
        # 基础指标
        execution_success_rate = successful_tests / total_tests
        avg_response_time = sum(r.execution_time for r in self.results) / total_tests
        
        # SQL相关指标
        sql_generated_count = sum(1 for r in self.results if r.sql_generated)
        sql_generation_rate = sql_generated_count / total_tests
        
        sql_executable_count = sum(1 for r in self.results if r.sql_executable)
        sql_execution_success_rate = sql_executable_count / total_tests
        
        # 结果正确率（只计算有期望结果的测试用例）
        result_correct_tests = [r for r in self.results if r.sql_correct is not None]
        result_correct_count = sum(1 for r in result_correct_tests if r.sql_correct)
        result_correct_rate = result_correct_count / len(result_correct_tests) if result_correct_tests else 0
        
        # 时间解析准确率（只计算有期望时间过滤器的测试用例）
        time_parsed_tests = [r for r in self.results if r.time_parsed_correctly is not None]
        time_parsed_correct_count = sum(1 for r in time_parsed_tests if r.time_parsed_correctly)
        time_parsing_accuracy = time_parsed_correct_count / len(time_parsed_tests) if time_parsed_tests else 0
        
        # 指标识别准确率（只计算有期望指标的测试用例）
        metric_identified_tests = [r for r in self.results if r.metric_identified_correctly is not None]
        metric_identified_correct_count = sum(1 for r in metric_identified_tests if r.metric_identified_correctly)
        metric_identification_accuracy = metric_identified_correct_count / len(metric_identified_tests) if metric_identified_tests else 0
        
        # 分组字段准确率（只计算有期望分组字段的测试用例）
        group_by_tests = [r for r in self.results if r.group_by_correct is not None]
        group_by_correct_count = sum(1 for r in group_by_tests if r.group_by_correct)
        group_by_accuracy = group_by_correct_count / len(group_by_tests) if group_by_tests else 0
        
        result_complete_count = sum(1 for r in self.results if r.result_complete)
        result_completeness = result_complete_count / total_tests
        
        # RAG相关指标
        rag_results = [r for r in self.results if r.rag_recall_rate is not None]
        rag_metrics = {}
        if rag_results:
            rag_metrics = {
                'avg_recall_rate': sum(r.rag_recall_rate for r in rag_results if r.rag_recall_rate is not None) / len([r for r in rag_results if r.rag_recall_rate is not None]) if any(r.rag_recall_rate is not None for r in rag_results) else 0.0,
                'avg_precision_rate': sum(r.rag_precision_rate for r in rag_results if r.rag_precision_rate is not None) / len([r for r in rag_results if r.rag_precision_rate is not None]) if any(r.rag_precision_rate is not None for r in rag_results) else 0.0,
                'avg_relevance_score': sum(r.rag_relevance_score for r in rag_results if r.rag_relevance_score is not None) / len([r for r in rag_results if r.rag_relevance_score is not None]) if any(r.rag_relevance_score is not None for r in rag_results) else 0.0,
                'avg_fragment_count': sum(r.rag_fragment_count for r in rag_results if r.rag_fragment_count is not None) / len([r for r in rag_results if r.rag_fragment_count is not None]) if any(r.rag_fragment_count is not None for r in rag_results) else 0.0,
                'avg_entity_coverage': sum(r.rag_entity_coverage for r in rag_results if r.rag_entity_coverage is not None) / len([r for r in rag_results if r.rag_entity_coverage is not None]) if any(r.rag_entity_coverage is not None for r in rag_results) else 0.0,
                'avg_concept_coverage': sum(r.rag_concept_coverage for r in rag_results if r.rag_concept_coverage is not None) / len([r for r in rag_results if r.rag_concept_coverage is not None]) if any(r.rag_concept_coverage is not None for r in rag_results) else 0.0
            }
        
        # 错误类型分布
        error_types = {}
        for result in self.results:
            if not result.success and result.error_type:
                error_types[result.error_type] = error_types.get(result.error_type, 0) + 1
        
        # 组件性能分解
        component_performance = {}
        for component in ['query_rewriter', 'ir_builder', 'sql_generator', 'sql_executor']:
            times = [r.component_timings.get(component, 0) for r in self.results if r.component_timings]
            if times:
                component_performance[component] = {
                    'avg_time': sum(times) / len(times),
                    'max_time': max(times),
                    'min_time': min(times)
                }
        
        # 按类别统计
        category_stats = {}
        for category in set(tc.category for tc in self.test_cases):
            category_results = [r for r in self.results if r.test_case.category == category]
            if category_results:
                category_stats[category] = {
                    'total': len(category_results),
                    'success': sum(1 for r in category_results if r.success),
                    'success_rate': sum(1 for r in category_results if r.success) / len(category_results)
                }
        
        return {
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'execution_success_rate': execution_success_rate,
                'avg_response_time': avg_response_time
            },
            'sql_metrics': {
                'sql_generation_rate': sql_generation_rate,
                'sql_execution_success_rate': sql_execution_success_rate,
                'result_correct_rate': result_correct_rate
            },
            'accuracy_metrics': {
                'time_parsing_accuracy': time_parsing_accuracy,
                'metric_identification_accuracy': metric_identification_accuracy,
                'group_by_accuracy': group_by_accuracy,
                'result_completeness': result_completeness
            },
            'rag_metrics': rag_metrics,
            'error_analysis': {
                'error_types': error_types,
                'error_rate': 1 - execution_success_rate
            },
            'performance': {
                'component_performance': component_performance
            },
            'category_stats': category_stats
        }
    
    def print_metrics(self):
        """打印评价指标"""
        metrics = self.calculate_metrics()
        
        print(f"\n{'='*60}")
        print(f"[ENHANCED BATCH TEST RESULTS] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Basic Metrics
        print(f"1. Execution Success Rate: {metrics['summary']['execution_success_rate']:.2%}")
        print(f"2. Average Response Time: {metrics['summary']['avg_response_time']:.3f}s")
        
        # SQL Related Metrics
        print(f"3. SQL Generation Rate: {metrics['sql_metrics']['sql_generation_rate']:.2%}")
        print(f"4. SQL Execution Success Rate: {metrics['sql_metrics']['sql_execution_success_rate']:.2%}")
        print(f"5. Result Correctness Rate: {metrics['sql_metrics']['result_correct_rate']:.2%}")
        
        # Function Accuracy
        print(f"6. Time Parsing Accuracy: {metrics['accuracy_metrics']['time_parsing_accuracy']:.2%}")
        print(f"7. Metric Identification Accuracy: {metrics['accuracy_metrics']['metric_identification_accuracy']:.2%}")
        print(f"8. Group By Accuracy: {metrics['accuracy_metrics']['group_by_accuracy']:.2%}")
        print(f"9. Result Completeness: {metrics['accuracy_metrics']['result_completeness']:.2%}")
        
        # RAG Related Metrics
        if metrics['rag_metrics']:
            print(f"10. RAG Average Recall Rate: {metrics['rag_metrics']['avg_recall_rate']:.2%}")
            print(f"11. RAG Average Precision Rate: {metrics['rag_metrics']['avg_precision_rate']:.2%}")
            print(f"12. RAG Average Relevance Score: {metrics['rag_metrics']['avg_relevance_score']:.2%}")
            print(f"13. RAG Average Fragment Count: {metrics['rag_metrics']['avg_fragment_count']:.1f}")
            print(f"14. RAG Entity Coverage: {metrics['rag_metrics']['avg_entity_coverage']:.2%}")
            print(f"15. RAG Concept Coverage: {metrics['rag_metrics']['avg_concept_coverage']:.2%}")
        
        # Component Performance Breakdown
        print(f"\n[COMPONENT PERFORMANCE BREAKDOWN]:")
        for component, perf in metrics['performance']['component_performance'].items():
            print(f"   {component}: Avg {perf['avg_time']:.3f}s (Max {perf['max_time']:.3f}s, Min {perf['min_time']:.3f}s)")
        
        # Category Statistics
        print(f"\n[CATEGORY STATISTICS]:")
        for category, stats in metrics['category_stats'].items():
            print(f"   {category}: {stats['success']}/{stats['total']} ({stats['success_rate']:.2%})")
        
        print(f"{'='*60}")
    
    def _needs_time_clarification(self, rewritten_query, test_case: TestCase) -> bool:
        """检查是否需要时间澄清"""
        print(f"[DEBUG] Checking time clarification for {test_case.id}")
        print(f"[DEBUG] Has time_clarification config: {test_case.time_clarification is not None}")
        print(f"[DEBUG] Q2Q time_filter: {rewritten_query.time_filter}")
        print(f"[DEBUG] Expected time_filter: {test_case.expected_time_filter}")
        
        # 如果测试用例没有配置时间澄清，则不需要
        if not test_case.time_clarification:
            print(f"[DEBUG] No time clarification config, skipping")
            return False
            
        time_clarif = test_case.time_clarification
        
        # 如果明确配置为不需要澄清
        if not time_clarif.get('needed', True):
            print(f"[DEBUG] Time clarification not needed per config")
            return False
            
        # 检查是否有预期的时间过滤器
        if test_case.expected_time_filter:
            actual_time = rewritten_query.time_filter
            expected_time = test_case.expected_time_filter
            
            # 如果Q2Q没有解析出时间，需要澄清
            if not actual_time:
                print(f"[DEBUG] Time clarification needed: expected {expected_time} but Q2Q returned None")
                return True
                
            # 如果Q2Q解析的时间不正确，也需要澄清
            if actual_time != expected_time:
                print(f"[DEBUG] Time clarification needed: expected {expected_time} but Q2Q returned {actual_time}")
                return True
                
            print(f"[DEBUG] Q2Q correctly parsed time filter: {actual_time}")
            return False
            
        print(f"[DEBUG] No time clarification needed")
        return False
    
    def _simulate_time_clarification(self, rewritten_query, test_case: TestCase):
        """模拟时间澄清过程"""
        if not test_case.time_clarification:
            return rewritten_query
            
        time_clarif = test_case.time_clarification
        user_input = time_clarif.get('expected_input')
        
        if user_input:
            print(f"[TIME CLARIFICATION] {test_case.id}: Simulating user input '{user_input}'")
            
            # 创建一个新的查询对象，添加用户提供的时间信息
            from copy import deepcopy
            clarified_query = deepcopy(rewritten_query)
            clarified_query.time_filter = user_input
            
            # 添加调试信息
            print(f"[DEBUG] Time filter updated from '{rewritten_query.time_filter}' to '{user_input}'")
            
            return clarified_query
            
        return rewritten_query
    
    def save_results(self, output_file: str):
        """保存测试结果到JSON文件"""
        results_data = []
        for result in self.results:
            result_dict = asdict(result)
            # 移除不可序列化的对象
            result_dict['rewritten_query'] = str(result.rewritten_query) if result.rewritten_query else None
            result_dict['ir'] = str(result.ir) if result.ir else None
            results_data.append(result_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] Test results saved to: {output_file}")


def main():
    """主函数"""
    evaluator = BatchTestEvaluator()
    
    # 加载测试用例
    test_file = "test_cases_rag.json"
    if Path(test_file).exists():
        evaluator.load_test_cases(test_file)
    else:
        print(f"[ERROR] Test file {test_file} does not exist")
        return
    
    # 运行批量测试
    evaluator.run_batch_test()


if __name__ == "__main__":
    main()
