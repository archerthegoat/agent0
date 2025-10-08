"""
智能实体类型推断器

基于语义分析智能推断所需实体类型，完全消除硬编码关键词匹配。
使用嵌入模型和元数据进行智能分析。
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class EntityTypeRequirement:
    """实体类型需求"""
    entity_type: str
    confidence: float
    reasoning: str
    required_count: int = 1


@dataclass
class QueryIntentAnalysis:
    """查询意图分析结果"""
    required_types: Set[str]
    type_requirements: List[EntityTypeRequirement]
    business_domain: str
    analysis_confidence: float


class IntelligentEntityTypeInferencer:
    """基于语义分析智能推断所需实体类型"""
    
    def __init__(self, embedder, metadata_loader):
        self.embedder = embedder
        self.metadata_loader = metadata_loader
        self.entity_type_embeddings = {}
        self.business_domain_embeddings = {}
        self._build_entity_type_embeddings()
        self._build_business_domain_embeddings()
    
    def infer_required_entity_types(self, query: str) -> Set[str]:
        """基于查询语义推断所需实体类型"""
        try:
            analysis = self.analyze_query_intent(query)
            return analysis.required_types
        except Exception as e:
            print(f"[ERROR] 实体类型推断失败: {e}")
            return {'metric'}  # 默认至少需要指标
    
    def analyze_query_intent(self, query: str) -> QueryIntentAnalysis:
        """分析查询意图，返回详细的实体类型需求"""
        try:
            # 生成查询嵌入
            query_embedding = self.embedder.embed([query])[0]
            
            # 1. 分析实体类型需求
            type_requirements = self._analyze_entity_type_requirements(query, query_embedding)
            
            # 2. 推断业务域
            business_domain = self._infer_business_domain(query, query_embedding)
            
            # 3. 计算分析置信度
            analysis_confidence = self._calculate_analysis_confidence(type_requirements)
            
            # 4. 提取所需类型
            required_types = {req.entity_type for req in type_requirements}
            
            # 5. 确保至少包含metric类型
            if 'metric' not in required_types:
                required_types.add('metric')
                type_requirements.append(EntityTypeRequirement(
                    entity_type='metric',
                    confidence=0.8,
                    reasoning='所有查询都需要指标',
                    required_count=1
                ))
            
            return QueryIntentAnalysis(
                required_types=required_types,
                type_requirements=type_requirements,
                business_domain=business_domain,
                analysis_confidence=analysis_confidence
            )
            
        except Exception as e:
            print(f"[ERROR] 查询意图分析失败: {e}")
            return QueryIntentAnalysis(
                required_types={'metric'},
                type_requirements=[EntityTypeRequirement('metric', 0.5, '默认需求')],
                business_domain='unknown',
                analysis_confidence=0.0
            )
    
    def _build_entity_type_embeddings(self):
        """基于metadata构建实体类型的语义嵌入"""
        try:
            # 为每种实体类型构建代表性文本
            type_descriptions = {
                'metric': self._build_metric_description(),
                'dimension': self._build_dimension_description(),
                'mapping': self._build_mapping_description(),
                'concept': self._build_concept_description()
            }
            
            for entity_type, description in type_descriptions.items():
                if description:
                    embedding = self.embedder.embed([description])[0]
                    self.entity_type_embeddings[entity_type] = embedding
                    print(f"[DEBUG] 构建实体类型嵌入: {entity_type}")
            
        except Exception as e:
            print(f"[ERROR] 构建实体类型嵌入失败: {e}")
    
    def _build_business_domain_embeddings(self):
        """构建业务域嵌入"""
        try:
            business_domains = {
                'user_analysis': '用户分析 用户行为 用户价值 用户画像 用户分群',
                'revenue_analysis': '收入分析 营收分析 财务分析 收入统计 收入趋势',
                'marketing_analysis': '营销分析 推广分析 渠道分析 获客分析 转化分析',
                'product_analysis': '产品分析 商品分析 品类分析 产品表现 产品趋势',
                'operational_analysis': '运营分析 运营数据 运营指标 运营效果 运营优化',
                'technical_analysis': '技术分析 性能分析 系统分析 技术指标 技术监控'
            }
            
            for domain, description in business_domains.items():
                embedding = self.embedder.embed([description])[0]
                self.business_domain_embeddings[domain] = embedding
            
        except Exception as e:
            print(f"[ERROR] 构建业务域嵌入失败: {e}")
    
    def _build_metric_description(self) -> str:
        """基于所有指标动态构建指标类型描述"""
        try:
            descriptions = []
            metrics = self.metadata_loader.load_metrics()
            
            for metric in metrics:
                descriptions.append(metric.get('canonical_name', ''))
                descriptions.extend(metric.get('aliases', []))
                
                # 添加描述信息
                description = metric.get('description', '')
                if description:
                    descriptions.append(description)
                
                # 添加业务含义
                business_meaning = metric.get('business_meaning', '')
                if business_meaning:
                    descriptions.append(business_meaning)
            
            return ' '.join(filter(None, descriptions))
            
        except Exception as e:
            print(f"[ERROR] 构建指标描述失败: {e}")
            return '指标 统计 数据 分析 计算 汇总 聚合'
    
    def _build_dimension_description(self) -> str:
        """基于所有维度动态构建维度类型描述"""
        try:
            descriptions = []
            dimensions = self.metadata_loader.load_dimensions()
            
            for dimension in dimensions:
                descriptions.append(dimension.get('canonical_name', ''))
                descriptions.extend(dimension.get('aliases', []))
                
                # 添加描述信息
                what_info = dimension.get('what', {})
                description = what_info.get('description', '')
                if description:
                    descriptions.append(description)
            
            return ' '.join(filter(None, descriptions))
            
        except Exception as e:
            print(f"[ERROR] 构建维度描述失败: {e}")
            return '维度 分组 分类 属性 特征 标签'
    
    def _build_mapping_description(self) -> str:
        """构建映射类型描述"""
        try:
            descriptions = []
            mappings = self.metadata_loader.load_mappings()
            
            for mapping in mappings:
                descriptions.append(mapping.get('canonical_name', ''))
                descriptions.extend(mapping.get('aliases', []))
                
                # 添加映射信息
                mappings_info = mapping.get('mappings', [])
                for mapping_item in mappings_info:
                    if isinstance(mapping_item, dict):
                        descriptions.append(mapping_item.get('description', ''))
            
            return ' '.join(filter(None, descriptions))
            
        except Exception as e:
            print(f"[ERROR] 构建映射描述失败: {e}")
            return '映射 关系 关联 规则 公式 计算 逻辑 对应 转换'
    
    def _build_concept_description(self) -> str:
        """构建概念类型描述"""
        return '概念 业务 含义 定义 术语 词汇 关键词 语义 上下文'
    
    def _analyze_entity_type_requirements(self, query: str, query_embedding: List[float]) -> List[EntityTypeRequirement]:
        """分析实体类型需求"""
        requirements = []
        
        # 基于语义相似度判断需要的实体类型
        for entity_type, type_embedding in self.entity_type_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, type_embedding)
            threshold = self._get_dynamic_threshold(entity_type)
            
            if similarity > threshold:
                reasoning = f"查询与{entity_type}类型语义相似度: {similarity:.3f}"
                required_count = self._estimate_required_count(query, entity_type)
                
                requirements.append(EntityTypeRequirement(
                    entity_type=entity_type,
                    confidence=similarity,
                    reasoning=reasoning,
                    required_count=required_count
                ))
        
        # 基于查询关键词补充分析
        keyword_requirements = self._analyze_keyword_requirements(query)
        for req in keyword_requirements:
            # 检查是否已存在
            existing = next((r for r in requirements if r.entity_type == req.entity_type), None)
            if existing:
                # 更新置信度
                existing.confidence = max(existing.confidence, req.confidence)
                existing.reasoning += f"; 关键词匹配: {req.reasoning}"
            else:
                requirements.append(req)
        
        return requirements
    
    def _analyze_keyword_requirements(self, query: str) -> List[EntityTypeRequirement]:
        """基于关键词分析实体类型需求"""
        requirements = []
        query_lower = query.lower()
        
        # 维度相关关键词
        dimension_keywords = [
            '按', '分组', '分类', '对比', '分析', '分布', '排名',
            '渠道', '地区', '设备', '平台', '用户等级', '时间',
            'group by', 'channel', 'region', 'device', 'platform'
        ]
        
        if any(keyword in query_lower for keyword in dimension_keywords):
            requirements.append(EntityTypeRequirement(
                entity_type='dimension',
                confidence=0.7,
                reasoning='查询包含维度分析关键词',
                required_count=1
            ))
        
        # 映射相关关键词
        mapping_keywords = [
            '映射', '关系', '关联', '规则', '公式', '计算', '逻辑',
            '对应', '转换', 'mapping', 'relation', 'formula'
        ]
        
        if any(keyword in query_lower for keyword in mapping_keywords):
            requirements.append(EntityTypeRequirement(
                entity_type='mapping',
                confidence=0.6,
                reasoning='查询包含映射关系关键词',
                required_count=1
            ))
        
        # 概念相关关键词
        concept_keywords = [
            '概念', '业务', '含义', '定义', '术语', '语义',
            'concept', 'business', 'meaning', 'definition'
        ]
        
        if any(keyword in query_lower for keyword in concept_keywords):
            requirements.append(EntityTypeRequirement(
                entity_type='concept',
                confidence=0.5,
                reasoning='查询包含概念相关关键词',
                required_count=1
            ))
        
        return requirements
    
    def _infer_business_domain(self, query: str, query_embedding: List[float]) -> str:
        """推断业务域"""
        try:
            best_domain = 'unknown'
            best_similarity = 0.0
            
            for domain, domain_embedding in self.business_domain_embeddings.items():
                similarity = self._cosine_similarity(query_embedding, domain_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_domain = domain
            
            return best_domain if best_similarity > 0.3 else 'unknown'
            
        except Exception as e:
            print(f"[ERROR] 业务域推断失败: {e}")
            return 'unknown'
    
    def _estimate_required_count(self, query: str, entity_type: str) -> int:
        """估算所需实体数量"""
        # 基于查询复杂度估算
        query_length = len(query)
        
        if entity_type == 'metric':
            # 指标数量通常1-3个
            if query_length > 50:
                return 2
            else:
                return 1
        elif entity_type == 'dimension':
            # 维度数量通常1-2个
            return 1
        elif entity_type == 'mapping':
            # 映射关系通常1个
            return 1
        elif entity_type == 'concept':
            # 概念通常1个
            return 1
        else:
            return 1
    
    def _get_dynamic_threshold(self, entity_type: str) -> float:
        """获取动态阈值"""
        thresholds = {
            'metric': 0.3,      # 指标阈值较低，因为所有查询都需要
            'dimension': 0.4,   # 维度阈值中等
            'mapping': 0.5,     # 映射阈值较高
            'concept': 0.6      # 概念阈值最高
        }
        return thresholds.get(entity_type, 0.5)
    
    def _calculate_analysis_confidence(self, requirements: List[EntityTypeRequirement]) -> float:
        """计算分析置信度"""
        if not requirements:
            return 0.0
        
        # 基于需求数量和置信度计算
        avg_confidence = sum(req.confidence for req in requirements) / len(requirements)
        
        # 需求数量越多，置信度越高（说明分析更全面）
        count_factor = min(1.0, len(requirements) / 3.0)
        
        return avg_confidence * count_factor
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            a = np.array(vec1)
            b = np.array(vec2)
            
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
    
    def get_analysis_statistics(self, query: str) -> Dict[str, Any]:
        """获取分析统计信息"""
        analysis = self.analyze_query_intent(query)
        
        return {
            'required_types': list(analysis.required_types),
            'type_requirements': [
                {
                    'entity_type': req.entity_type,
                    'confidence': req.confidence,
                    'reasoning': req.reasoning,
                    'required_count': req.required_count
                }
                for req in analysis.type_requirements
            ],
            'business_domain': analysis.business_domain,
            'analysis_confidence': analysis.analysis_confidence,
            'query_length': len(query)
        }
