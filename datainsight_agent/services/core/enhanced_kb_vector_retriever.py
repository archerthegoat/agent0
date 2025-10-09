"""
增强版KB向量检索器

集成所有新组件，提供完全数据驱动的RAG检索能力。
消除所有硬编码，支持任意数量的指标和维度。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from datainsight_agent.services.core.dynamic_pattern_generator import DynamicPatternGenerator
from datainsight_agent.services.core.adaptive_relevance_calculator import AdaptiveRelevanceCalculator
from datainsight_agent.services.core.intelligent_entity_type_inferencer import IntelligentEntityTypeInferencer
from datainsight_agent.services.core.type_aware_retrieval_strategy import TypeAwareRetrievalStrategy
from datainsight_agent.services.core.metadata_loader import MetadataLoader
from datainsight_agent.clients.vector_store import EmbeddingModel

# 设置日志记录器
logger = logging.getLogger(__name__)


class EnhancedKBVectorRetriever:
    """增强版KB向量检索器，完全数据驱动"""
    
    def __init__(self, index_dir: str | Path = "kb_vector_index", metadata_dir: str | Path = "metadata"):
        self.index_dir = Path(index_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # 初始化组件
        self.metadata_loader = MetadataLoader(metadata_dir)
        self.pattern_generator = DynamicPatternGenerator(metadata_dir)
        self.embedder = EmbeddingModel()
        
        # 初始化计算器
        self.relevance_calculator = AdaptiveRelevanceCalculator(
            self.embedder, 
            self.metadata_loader
        )
        
        # 初始化推断器
        self.entity_type_inferencer = IntelligentEntityTypeInferencer(
            self.embedder,
            self.metadata_loader
        )
        
        # 初始化检索策略（需要原有的向量检索器）
        self.vector_retriever = None  # 将在_load_vector_retriever中初始化
        self.retrieval_strategy = None  # 将在_load_vector_retriever中初始化
        
        # 加载向量检索器
        self._load_vector_retriever()
    
    def _load_vector_retriever(self):
        """加载原有的向量检索器"""
        try:
            from datainsight_agent.services.core.kb_vector_index import KBVectorRetriever
            self.vector_retriever = KBVectorRetriever(self.index_dir)
            
            # 初始化检索策略
            self.retrieval_strategy = TypeAwareRetrievalStrategy(
                self.vector_retriever,
                self.entity_type_inferencer,
                self.relevance_calculator
            )
            
            logger.info("增强版KB向量检索器初始化成功")
            
        except Exception as e:
            logger.error(f"加载向量检索器失败: {e}")
            self.vector_retriever = None
            self.retrieval_strategy = None
    
    def search_with_enhanced_rag(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """使用增强RAG进行检索"""
        try:
            # 1. 使用类型感知检索策略
            retrieval_result = self.retrieval_strategy.retrieve_with_type_diversity(query, top_k)
            
            # 2. 计算综合相关性评分
            comprehensive_relevance = self.relevance_calculator.calculate_comprehensive_relevance(
                query, retrieval_result.fragments
            )
            
            # 3. 分析查询意图
            intent_analysis = self.entity_type_inferencer.analyze_query_intent(query)
            
            # 4. 获取动态模式
            relevant_patterns = self.pattern_generator.get_patterns_for_query(query)
            
            # 5. 构建增强的RAG上下文
            enhanced_context = self._build_enhanced_context(
                query, 
                retrieval_result.fragments, 
                comprehensive_relevance,
                intent_analysis
            )
            
            return {
                'fragments': retrieval_result.fragments,
                'context': enhanced_context,
                'relevance_score': comprehensive_relevance.overall_score,
                'semantic_similarity': comprehensive_relevance.semantic_similarity,
                'fragment_quality': comprehensive_relevance.fragment_quality,
                'business_relevance': comprehensive_relevance.business_relevance,
                'confidence': comprehensive_relevance.confidence,
                'type_coverage': retrieval_result.type_coverage,
                'diversity_score': retrieval_result.diversity_score,
                'required_types': list(intent_analysis.required_types),
                'business_domain': intent_analysis.business_domain,
                'analysis_confidence': intent_analysis.analysis_confidence,
                'relevant_patterns': relevant_patterns,
                'retrieval_strategy': retrieval_result.retrieval_strategy
            }
            
        except Exception as e:
            logger.error(f"增强RAG检索失败: {e}")
            return self._fallback_search(query, top_k)
    
    def _build_enhanced_context(self, query: str, fragments: List[Dict], relevance_score, intent_analysis) -> str:
        """构建增强的RAG上下文"""
        context_parts = []
        
        # 1. 添加查询意图信息
        context_parts.append(f"查询意图: {intent_analysis.business_domain}")
        context_parts.append(f"所需实体类型: {', '.join(intent_analysis.required_types)}")
        
        # 2. 添加相关性信息
        context_parts.append(f"语义相关性: {relevance_score.semantic_similarity:.3f}")
        context_parts.append(f"业务相关性: {relevance_score.business_relevance:.3f}")
        context_parts.append(f"综合置信度: {relevance_score.confidence:.3f}")
        
        # 3. 添加片段信息
        for i, fragment in enumerate(fragments):
            metadata = fragment.get('metadata', {})
            entity_type = fragment.get('entity_type', '')
            canonical_name = metadata.get('canonical_name', '')
            aliases = metadata.get('aliases', [])
            description = metadata.get('description', '')
            
            fragment_info = f"片段{i+1} ({entity_type}): {canonical_name}"
            if aliases:
                fragment_info += f" [别名: {', '.join(aliases[:3])}]"
            if description:
                fragment_info += f" - {description[:100]}..."
            
            context_parts.append(fragment_info)
        
        return "\n".join(context_parts)
    
    def _fallback_search(self, query: str, top_k: int) -> Dict[str, Any]:
        """回退检索"""
        try:
            if self.vector_retriever:
                fragments = self.vector_retriever.search_topics_and_metrics(query, top_k)
                context = f"回退检索结果: {len(fragments)} 个片段"
            else:
                fragments = []
                context = "检索失败"
            
            return {
                'fragments': fragments,
                'context': context,
                'relevance_score': 0.0,
                'semantic_similarity': 0.0,
                'fragment_quality': 0.0,
                'business_relevance': 0.0,
                'confidence': 0.0,
                'type_coverage': {},
                'diversity_score': 0.0,
                'required_types': [],
                'business_domain': 'unknown',
                'analysis_confidence': 0.0,
                'relevant_patterns': {},
                'retrieval_strategy': 'fallback'
            }
            
        except Exception as e:
            logger.error(f"回退检索失败: {e}")
            return {
                'fragments': [],
                'context': '检索完全失败',
                'relevance_score': 0.0,
                'semantic_similarity': 0.0,
                'fragment_quality': 0.0,
                'business_relevance': 0.0,
                'confidence': 0.0,
                'type_coverage': {},
                'diversity_score': 0.0,
                'required_types': [],
                'business_domain': 'unknown',
                'analysis_confidence': 0.0,
                'relevant_patterns': {},
                'retrieval_strategy': 'error'
            }
    
    def get_enhanced_statistics(self, query: str) -> Dict[str, Any]:
        """获取增强统计信息"""
        try:
            # 获取各组件统计信息
            metadata_stats = self.metadata_loader.get_statistics()
            retrieval_stats = self.retrieval_strategy.get_retrieval_statistics(query) if self.retrieval_strategy else {}
            analysis_stats = self.entity_type_inferencer.get_analysis_statistics(query)
            relevance_stats = self.relevance_calculator.get_relevance_statistics(query, [])
            
            return {
                'metadata': metadata_stats,
                'retrieval': retrieval_stats,
                'analysis': analysis_stats,
                'relevance': relevance_stats,
                'query_length': len(query),
                'components_loaded': {
                    'pattern_generator': self.pattern_generator is not None,
                    'relevance_calculator': self.relevance_calculator is not None,
                    'entity_type_inferencer': self.entity_type_inferencer is not None,
                    'retrieval_strategy': self.retrieval_strategy is not None,
                    'vector_retriever': self.vector_retriever is not None
                }
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def update_configuration(self, config: Dict[str, Any]):
        """更新配置"""
        try:
            # 更新相关性计算器权重
            if 'relevance_weights' in config:
                self.relevance_calculator.update_weights(config['relevance_weights'])
            
            # 更新检索策略配置
            if 'retrieval_strategy' in config:
                self.retrieval_strategy.update_strategy_config(config['retrieval_strategy'])
            
            logger.info(f"配置已更新: {config}")
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
    
    def clear_all_caches(self):
        """清除所有缓存"""
        try:
            self.metadata_loader.clear_cache()
            self.pattern_generator.clear_cache()
            logger.info("所有缓存已清除")
            
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
    
    def validate_system(self) -> Dict[str, Any]:
        """验证系统状态"""
        validation_results = {
            'metadata_loaded': False,
            'patterns_generated': False,
            'embeddings_working': False,
            'retrieval_working': False,
            'overall_status': 'unknown'
        }
        
        try:
            # 验证元数据加载
            metrics = self.metadata_loader.load_metrics()
            dimensions = self.metadata_loader.load_dimensions()
            validation_results['metadata_loaded'] = len(metrics) > 0 and len(dimensions) > 0
            
            # 验证模式生成
            patterns = self.pattern_generator.get_all_patterns()
            validation_results['patterns_generated'] = len(patterns.get('metrics', {})) > 0
            
            # 验证嵌入模型
            test_embedding = self.embedder.embed(["测试文本"])
            validation_results['embeddings_working'] = len(test_embedding) > 0 and len(test_embedding[0]) > 0
            
            # 验证检索功能
            if self.vector_retriever:
                test_fragments = self.vector_retriever.search_topics_and_metrics("测试查询", 1)
                validation_results['retrieval_working'] = True  # 不检查结果，只检查是否出错
            
            # 计算总体状态
            all_working = all(validation_results[key] for key in ['metadata_loaded', 'patterns_generated', 'embeddings_working', 'retrieval_working'])
            validation_results['overall_status'] = 'healthy' if all_working else 'degraded'
            
        except Exception as e:
            logger.error(f"系统验证失败: {e}")
            validation_results['overall_status'] = 'error'
        
        return validation_results
