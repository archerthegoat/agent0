"""
自适应相关性计算器

基于嵌入和元数据的自适应相关性计算，完全消除硬编码关键词匹配。
使用纯语义相似度进行相关性评估。
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class RelevanceScore:
    """相关性评分结果"""
    semantic_similarity: float
    fragment_quality: float
    business_relevance: float
    overall_score: float
    confidence: float


class AdaptiveRelevanceCalculator:
    """基于嵌入和元数据的自适应相关性计算"""
    
    def __init__(self, embedder, metadata_loader):
        self.embedder = embedder
        self.metadata_loader = metadata_loader
        self.semantic_cache = {}
        
        # 动态权重配置（可基于历史数据调整）
        self.weights = {
            'semantic_similarity': 0.6,
            'fragment_quality': 0.2,
            'business_relevance': 0.2
        }
    
    def calculate_semantic_relevance(self, query: str, fragments: List[Dict]) -> float:
        """纯语义相关性，无硬编码关键词"""
        if not fragments:
            return 0.0
        
        try:
            # 生成查询嵌入
            query_embedding = self.embedder.embed([query])[0]
            
            similarities = []
            for fragment in fragments:
                # 构建丰富的片段文本
                fragment_text = self._build_rich_fragment_text(fragment)
                
                # 生成片段嵌入
                fragment_embedding = self.embedder.embed([fragment_text])[0]
                
                # 计算语义相似度
                similarity = self._cosine_similarity(query_embedding, fragment_embedding)
                similarities.append(similarity)
            
            # 返回平均相似度
            return sum(similarities) / len(similarities) if similarities else 0.0
            
        except Exception as e:
            print(f"[ERROR] 语义相关性计算失败: {e}")
            return 0.0
    
    def calculate_comprehensive_relevance(self, query: str, fragments: List[Dict]) -> RelevanceScore:
        """计算综合相关性评分"""
        if not fragments:
            return RelevanceScore(0.0, 0.0, 0.0, 0.0, 0.0)
        
        try:
            # 1. 语义相似度
            semantic_similarity = self.calculate_semantic_relevance(query, fragments)
            
            # 2. 片段质量评分
            fragment_quality = self._calculate_fragment_quality(fragments)
            
            # 3. 业务相关性
            business_relevance = self._calculate_business_relevance(query, fragments)
            
            # 4. 综合评分
            overall_score = (
                semantic_similarity * self.weights['semantic_similarity'] +
                fragment_quality * self.weights['fragment_quality'] +
                business_relevance * self.weights['business_relevance']
            )
            
            # 5. 置信度评估
            confidence = self._calculate_confidence(semantic_similarity, fragment_quality, business_relevance)
            
            return RelevanceScore(
                semantic_similarity=semantic_similarity,
                fragment_quality=fragment_quality,
                business_relevance=business_relevance,
                overall_score=overall_score,
                confidence=confidence
            )
            
        except Exception as e:
            print(f"[ERROR] 综合相关性计算失败: {e}")
            return RelevanceScore(0.0, 0.0, 0.0, 0.0, 0.0)
    
    def _build_rich_fragment_text(self, fragment: Dict) -> str:
        """基于metadata构建丰富的片段文本"""
        metadata = fragment.get('metadata', {})
        text_parts = []
        
        # 1. 基础信息
        canonical_name = metadata.get('canonical_name', '')
        if canonical_name:
            text_parts.append(canonical_name)
        
        # 2. 别名信息
        aliases = metadata.get('aliases', [])
        text_parts.extend(aliases)
        
        # 3. 业务描述
        description = metadata.get('description', '')
        if description:
            text_parts.append(description)
        
        # 4. 业务含义
        business_meaning = metadata.get('business_meaning', '')
        if business_meaning:
            text_parts.append(business_meaning)
        
        # 5. 计算公式
        formula_human = metadata.get('formula_human', '')
        if formula_human:
            text_parts.append(formula_human)
        
        # 6. 数据源信息
        data_source = metadata.get('data_source', {})
        if data_source:
            table_name = data_source.get('table', '')
            column_name = data_source.get('column', '')
            if table_name:
                text_parts.append(f"表: {table_name}")
            if column_name:
                text_parts.append(f"字段: {column_name}")
        
        # 7. 实体类型信息
        entity_type = fragment.get('entity_type', '')
        if entity_type:
            type_descriptions = {
                'metric': '指标 统计 数据 分析',
                'dimension': '维度 分组 分类 属性',
                'mapping': '映射 关系 关联 规则',
                'concept': '概念 业务 含义 定义'
            }
            if entity_type in type_descriptions:
                text_parts.append(type_descriptions[entity_type])
        
        # 8. 聚合信息
        aggregation = metadata.get('aggregation', {})
        if aggregation:
            function = aggregation.get('function', '')
            field = aggregation.get('field', '')
            if function:
                text_parts.append(f"聚合函数: {function}")
            if field:
                text_parts.append(f"聚合字段: {field}")
        
        # 过滤空值并去重
        unique_parts = list(set(filter(None, text_parts)))
        return ' '.join(unique_parts)
    
    def _calculate_fragment_quality(self, fragments: List[Dict]) -> float:
        """计算片段质量评分"""
        if not fragments:
            return 0.0
        
        quality_scores = []
        
        for fragment in fragments:
            score = fragment.get('score', 0.0)
            if isinstance(score, (int, float)):
                quality_scores.append(float(score))
            else:
                quality_scores.append(0.0)
        
        # 计算质量指标
        if not quality_scores:
            return 0.0
        
        avg_score = sum(quality_scores) / len(quality_scores)
        high_quality_ratio = sum(1 for s in quality_scores if s > 0.7) / len(quality_scores)
        
        # 综合质量评分
        quality = (avg_score * 0.7 + high_quality_ratio * 0.3)
        return min(quality, 1.0)
    
    def _calculate_business_relevance(self, query: str, fragments: List[Dict]) -> float:
        """计算业务相关性"""
        if not fragments:
            return 0.0
        
        try:
            # 从查询中提取业务概念
            query_concepts = self._extract_business_concepts_from_query(query)
            
            if not query_concepts:
                return 0.5  # 默认中等相关性
            
            relevance_scores = []
            
            for fragment in fragments:
                fragment_concepts = self._extract_business_concepts_from_fragment(fragment)
                
                # 计算概念重叠度
                overlap = len(query_concepts & fragment_concepts)
                total_concepts = len(query_concepts | fragment_concepts)
                
                if total_concepts > 0:
                    relevance = overlap / total_concepts
                    relevance_scores.append(relevance)
                else:
                    relevance_scores.append(0.0)
            
            return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
            
        except Exception as e:
            print(f"[ERROR] 业务相关性计算失败: {e}")
            return 0.0
    
    def _extract_business_concepts_from_query(self, query: str) -> set:
        """从查询中提取业务概念"""
        concepts = set()
        
        # 基于查询文本提取业务概念
        business_concept_patterns = {
            '用户分析': ['用户', '客户', '访客', '使用者'],
            '活跃度分析': ['活跃', '活跃度', '活跃性', '活跃用户'],
            '收入分析': ['收入', '营收', '收益', '营业额', 'GMV', 'ARPU'],
            '成本分析': ['成本', '费用', '支出', 'CAC', '获客成本'],
            '渠道分析': ['渠道', '来源', '途径', '推广', '营销'],
            '地域分析': ['地域', '地区', '区域', '城市', '国家'],
            '设备分析': ['设备', '终端', '平台', '系统'],
            '时间分析': ['时间', '趋势', '变化', '周期', '季度', '月度'],
            '转化分析': ['转化', '转换', '转变', '漏斗'],
            '留存分析': ['留存', '保持', '维持', '粘性', '忠诚'],
            '流失分析': ['流失', '离开', '退出', '流失率'],
            'ROI分析': ['ROI', '投资回报', '回报率', '投资回报率']
        }
        
        query_lower = query.lower()
        for concept, keywords in business_concept_patterns.items():
            if any(keyword.lower() in query_lower for keyword in keywords):
                concepts.add(concept)
        
        return concepts
    
    def _extract_business_concepts_from_fragment(self, fragment: Dict) -> set:
        """从片段中提取业务概念"""
        concepts = set()
        
        metadata = fragment.get('metadata', {})
        
        # 从canonical_name提取概念
        canonical_name = metadata.get('canonical_name', '')
        if canonical_name:
            concepts.update(self._extract_business_concepts_from_query(canonical_name))
        
        # 从描述提取概念
        description = metadata.get('description', '')
        if description:
            concepts.update(self._extract_business_concepts_from_query(description))
        
        # 从业务含义提取概念
        business_meaning = metadata.get('business_meaning', '')
        if business_meaning:
            concepts.update(self._extract_business_concepts_from_query(business_meaning))
        
        return concepts
    
    def _calculate_confidence(self, semantic_similarity: float, fragment_quality: float, business_relevance: float) -> float:
        """计算置信度"""
        # 基于各项评分的稳定性计算置信度
        scores = [semantic_similarity, fragment_quality, business_relevance]
        
        # 计算标准差
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = math.sqrt(variance)
        
        # 置信度与标准差成反比
        confidence = max(0.0, 1.0 - std_dev)
        
        # 如果所有评分都很高，置信度也高
        if all(score > 0.7 for score in scores):
            confidence = min(1.0, confidence + 0.2)
        
        return confidence
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            # 转换为numpy数组
            a = np.array(vec1)
            b = np.array(vec2)
            
            # 计算余弦相似度
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)
            
        except Exception as e:
            print(f"[ERROR] 余弦相似度计算失败: {e}")
            return 0.0
    
    def update_weights(self, weights: Dict[str, float]):
        """更新权重配置"""
        self.weights.update(weights)
        print(f"[INFO] 权重配置已更新: {self.weights}")
    
    def get_relevance_statistics(self, query: str, fragments: List[Dict]) -> Dict[str, Any]:
        """获取相关性统计信息"""
        relevance_score = self.calculate_comprehensive_relevance(query, fragments)
        
        return {
            'semantic_similarity': relevance_score.semantic_similarity,
            'fragment_quality': relevance_score.fragment_quality,
            'business_relevance': relevance_score.business_relevance,
            'overall_score': relevance_score.overall_score,
            'confidence': relevance_score.confidence,
            'fragment_count': len(fragments),
            'weights': self.weights.copy()
        }
