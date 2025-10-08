"""
类型感知检索策略

基于推断的实体类型需求进行检索，确保检索结果包含所需的实体类型多样性。
完全消除硬编码的类型强制逻辑。
"""

from __future__ import annotations

from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass
import random


@dataclass
class RetrievalResult:
    """检索结果"""
    fragments: List[Dict[str, Any]]
    type_coverage: Dict[str, int]
    diversity_score: float
    relevance_score: float
    retrieval_strategy: str


@dataclass
class TypeSpecificQuery:
    """类型特定查询"""
    entity_type: str
    query_text: str
    priority: float
    expected_count: int


class TypeAwareRetrievalStrategy:
    """基于推断的实体类型需求进行检索"""
    
    def __init__(self, vector_retriever, entity_type_inferencer, relevance_calculator):
        self.vector_retriever = vector_retriever
        self.entity_type_inferencer = entity_type_inferencer
        self.relevance_calculator = relevance_calculator
        
        # 检索策略配置
        self.strategy_config = {
            'max_fragments_per_type': 3,
            'min_fragments_per_type': 1,
            'diversity_weight': 0.3,
            'relevance_weight': 0.7,
            'fallback_enabled': True
        }
    
    def retrieve_with_type_diversity(self, query: str, top_k: int = 5) -> RetrievalResult:
        """确保检索结果包含所需的实体类型"""
        try:
            # 1. 分析查询意图，推断所需实体类型
            intent_analysis = self.entity_type_inferencer.analyze_query_intent(query)
            required_types = intent_analysis.required_types
            
            print(f"[DEBUG] 推断所需实体类型: {required_types}")
            
            # 2. 为每种类型构建特定查询
            type_queries = self._build_type_specific_queries(query, intent_analysis.type_requirements)
            
            # 3. 执行类型感知检索
            all_fragments = []
            type_coverage = {}
            
            for type_query in type_queries:
                type_fragments = self._retrieve_for_type(type_query)
                all_fragments.extend(type_fragments)
                type_coverage[type_query.entity_type] = len(type_fragments)
            
            # 4. 如果某些类型缺失，尝试补充
            if self.strategy_config['fallback_enabled']:
                missing_types = required_types - set(type_coverage.keys())
                for missing_type in missing_types:
                    fallback_fragments = self._get_fallback_for_type(missing_type, query)
                    all_fragments.extend(fallback_fragments)
                    type_coverage[missing_type] = len(fallback_fragments)
            
            # 5. 去重和排序
            unique_fragments = self._deduplicate_fragments(all_fragments)
            ranked_fragments = self._rank_fragments(unique_fragments, query, required_types)
            
            # 6. 计算多样性评分
            diversity_score = self._calculate_diversity_score(type_coverage, required_types)
            
            # 7. 计算相关性评分
            relevance_score = self.relevance_calculator.calculate_semantic_relevance(query, ranked_fragments)
            
            # 8. 选择最佳结果
            final_fragments = self._select_best_fragments(ranked_fragments, top_k, required_types)
            
            return RetrievalResult(
                fragments=final_fragments,
                type_coverage=type_coverage,
                diversity_score=diversity_score,
                relevance_score=relevance_score,
                retrieval_strategy='type_aware'
            )
            
        except Exception as e:
            print(f"[ERROR] 类型感知检索失败: {e}")
            # 回退到基础检索
            return self._fallback_retrieval(query, top_k)
    
    def _build_type_specific_queries(self, original_query: str, type_requirements: List) -> List[TypeSpecificQuery]:
        """为每种类型构建特定查询"""
        type_queries = []
        
        for req in type_requirements:
            # 基于实体类型和原始查询构建特定查询
            specific_query = self._enhance_query_for_type(original_query, req.entity_type)
            
            type_queries.append(TypeSpecificQuery(
                entity_type=req.entity_type,
                query_text=specific_query,
                priority=req.confidence,
                expected_count=req.required_count
            ))
        
        return type_queries
    
    def _enhance_query_for_type(self, original_query: str, entity_type: str) -> str:
        """为特定实体类型增强查询"""
        type_enhancements = {
            'metric': '指标 统计 数据 分析 计算',
            'dimension': '维度 分组 分类 属性 特征',
            'mapping': '映射 关系 关联 规则 公式',
            'concept': '概念 业务 含义 定义 术语'
        }
        
        enhancement = type_enhancements.get(entity_type, '')
        if enhancement:
            return f"{original_query} {enhancement}"
        else:
            return original_query
    
    def _retrieve_for_type(self, type_query: TypeSpecificQuery) -> List[Dict[str, Any]]:
        """为特定类型执行检索"""
        try:
            # 使用现有的向量检索器
            fragments = self.vector_retriever.search_topics_and_metrics(
                type_query.query_text, 
                top_k=type_query.expected_count * 2  # 检索更多候选
            )
            
            # 过滤出指定类型的片段
            type_fragments = [
                fragment for fragment in fragments
                if fragment.get('entity_type') == type_query.entity_type
            ]
            
            # 按分数排序
            type_fragments.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 返回最佳结果
            return type_fragments[:type_query.expected_count]
            
        except Exception as e:
            print(f"[ERROR] 类型特定检索失败: {e}")
            return []
    
    def _get_fallback_for_type(self, entity_type: str, query: str) -> List[Dict[str, Any]]:
        """为缺失类型获取回退结果"""
        try:
            # 构建回退查询
            fallback_query = self._enhance_query_for_type(query, entity_type)
            
            # 执行检索
            fragments = self.vector_retriever.search_topics_and_metrics(fallback_query, top_k=5)
            
            # 过滤类型
            type_fragments = [
                fragment for fragment in fragments
                if fragment.get('entity_type') == entity_type
            ]
            
            # 如果仍然没有找到，尝试降低阈值
            if not type_fragments:
                type_fragments = self._try_lower_threshold_retrieval(entity_type, query)
            
            return type_fragments[:1]  # 只返回一个回退结果
            
        except Exception as e:
            print(f"[ERROR] 回退检索失败: {e}")
            return []
    
    def _try_lower_threshold_retrieval(self, entity_type: str, query: str) -> List[Dict[str, Any]]:
        """尝试降低阈值检索"""
        try:
            # 这里可以调用向量检索器的低阈值检索方法
            # 暂时返回空列表，实际实现时需要调用相应的方法
            return []
        except Exception as e:
            print(f"[ERROR] 低阈值检索失败: {e}")
            return []
    
    def _deduplicate_fragments(self, fragments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重片段"""
        seen_ids = set()
        unique_fragments = []
        
        for fragment in fragments:
            entity_id = fragment.get('entity_id', '')
            if entity_id and entity_id not in seen_ids:
                seen_ids.add(entity_id)
                unique_fragments.append(fragment)
        
        return unique_fragments
    
    def _rank_fragments(self, fragments: List[Dict[str, Any]], query: str, required_types: Set[str]) -> List[Dict[str, Any]]:
        """对片段进行排序"""
        try:
            # 计算每个片段的综合评分
            scored_fragments = []
            
            for fragment in fragments:
                # 基础分数
                base_score = fragment.get('score', 0.0)
                
                # 类型匹配奖励
                entity_type = fragment.get('entity_type', '')
                type_bonus = 0.1 if entity_type in required_types else 0.0
                
                # 语义相关性评分
                semantic_score = self.relevance_calculator.calculate_semantic_relevance(
                    query, [fragment]
                )
                
                # 综合评分
                final_score = (
                    base_score * self.strategy_config['relevance_weight'] +
                    semantic_score * self.strategy_config['relevance_weight'] +
                    type_bonus
                )
                
                scored_fragments.append((fragment, final_score))
            
            # 按评分排序
            scored_fragments.sort(key=lambda x: x[1], reverse=True)
            
            return [fragment for fragment, score in scored_fragments]
            
        except Exception as e:
            print(f"[ERROR] 片段排序失败: {e}")
            return fragments
    
    def _calculate_diversity_score(self, type_coverage: Dict[str, int], required_types: Set[str]) -> float:
        """计算多样性评分"""
        if not required_types:
            return 0.0
        
        # 计算覆盖率
        covered_types = set(type_coverage.keys()) & required_types
        coverage_ratio = len(covered_types) / len(required_types)
        
        # 计算分布均匀性
        if type_coverage:
            counts = list(type_coverage.values())
            if counts:
                # 计算变异系数（标准差/均值）
                mean_count = sum(counts) / len(counts)
                if mean_count > 0:
                    variance = sum((count - mean_count) ** 2 for count in counts) / len(counts)
                    std_dev = variance ** 0.5
                    cv = std_dev / mean_count
                    uniformity = max(0, 1 - cv)  # 变异系数越小，均匀性越好
                else:
                    uniformity = 0.0
            else:
                uniformity = 0.0
        else:
            uniformity = 0.0
        
        # 综合多样性评分
        diversity_score = coverage_ratio * 0.7 + uniformity * 0.3
        return min(diversity_score, 1.0)
    
    def _select_best_fragments(self, ranked_fragments: List[Dict[str, Any]], top_k: int, required_types: Set[str]) -> List[Dict[str, Any]]:
        """选择最佳片段"""
        if len(ranked_fragments) <= top_k:
            return ranked_fragments
        
        # 确保类型多样性
        selected_fragments = []
        type_counts = {t: 0 for t in required_types}
        
        # 首先选择每种类型的最佳片段
        for fragment in ranked_fragments:
            entity_type = fragment.get('entity_type', '')
            if entity_type in required_types and type_counts[entity_type] < 1:
                selected_fragments.append(fragment)
                type_counts[entity_type] += 1
        
        # 然后按评分选择剩余片段
        for fragment in ranked_fragments:
            if len(selected_fragments) >= top_k:
                break
            if fragment not in selected_fragments:
                selected_fragments.append(fragment)
        
        return selected_fragments[:top_k]
    
    def _fallback_retrieval(self, query: str, top_k: int) -> RetrievalResult:
        """回退检索策略"""
        try:
            # 使用基础检索
            fragments = self.vector_retriever.search_topics_and_metrics(query, top_k)
            
            return RetrievalResult(
                fragments=fragments,
                type_coverage={'unknown': len(fragments)},
                diversity_score=0.0,
                relevance_score=0.0,
                retrieval_strategy='fallback'
            )
            
        except Exception as e:
            print(f"[ERROR] 回退检索失败: {e}")
            return RetrievalResult(
                fragments=[],
                type_coverage={},
                diversity_score=0.0,
                relevance_score=0.0,
                retrieval_strategy='error'
            )
    
    def update_strategy_config(self, config: Dict[str, Any]):
        """更新策略配置"""
        self.strategy_config.update(config)
        print(f"[INFO] 检索策略配置已更新: {self.strategy_config}")
    
    def get_retrieval_statistics(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """获取检索统计信息"""
        result = self.retrieve_with_type_diversity(query, top_k)
        
        return {
            'fragment_count': len(result.fragments),
            'type_coverage': result.type_coverage,
            'diversity_score': result.diversity_score,
            'relevance_score': result.relevance_score,
            'retrieval_strategy': result.retrieval_strategy,
            'fragments_by_type': self._group_fragments_by_type(result.fragments)
        }
    
    def _group_fragments_by_type(self, fragments: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """按类型分组片段"""
        grouped = {}
        
        for fragment in fragments:
            entity_type = fragment.get('entity_type', 'unknown')
            entity_id = fragment.get('entity_id', '')
            
            if entity_type not in grouped:
                grouped[entity_type] = []
            
            if entity_id:
                grouped[entity_type].append(entity_id)
        
        return grouped
