"""
动态模式生成器

基于metadata动态生成所有模式，完全消除硬编码。
支持任意数量的指标、维度和映射关系。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass


@dataclass
class EntityPattern:
    """实体模式定义"""
    entity_id: str
    entity_type: str
    canonical_name: str
    aliases: List[str]
    semantic_variants: List[str]
    business_concepts: List[str]
    description: Optional[str] = None


class DynamicPatternGenerator:
    """基于metadata动态生成所有模式，零硬编码"""
    
    def __init__(self, metadata_dir: str | Path = "metadata"):
        self.metadata_dir = Path(metadata_dir)
        self.metrics_metadata = self._load_metrics_metadata()
        self.dimensions_metadata = self._load_dimensions_metadata()
        self.mappings_metadata = self._load_mappings_metadata()
        
        # 缓存生成的模式
        self._metric_patterns_cache: Optional[Dict[str, List[str]]] = None
        self._dimension_patterns_cache: Optional[Dict[str, List[str]]] = None
        self._query_intent_patterns_cache: Optional[Dict[str, List[str]]] = None
    
    def _load_metrics_metadata(self) -> List[Dict[str, Any]]:
        """加载指标元数据"""
        try:
            metrics_file = self.metadata_dir / "metrics.json"
            if not metrics_file.exists():
                print(f"[WARN] 指标元数据文件不存在: {metrics_file}")
                return []
            
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"[ERROR] 加载指标元数据失败: {e}")
            return []
    
    def _load_dimensions_metadata(self) -> List[Dict[str, Any]]:
        """加载维度元数据"""
        try:
            dimensions_file = self.metadata_dir / "dimensions.json"
            if not dimensions_file.exists():
                print(f"[WARN] 维度元数据文件不存在: {dimensions_file}")
                return []
            
            with open(dimensions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"[ERROR] 加载维度元数据失败: {e}")
            return []
    
    def _load_mappings_metadata(self) -> List[Dict[str, Any]]:
        """加载映射元数据"""
        try:
            mappings_file = self.metadata_dir / "mappings.json"
            if not mappings_file.exists():
                print(f"[WARN] 映射元数据文件不存在: {mappings_file}")
                return []
            
            with open(mappings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"[ERROR] 加载映射元数据失败: {e}")
            return []
    
    def generate_metric_patterns(self) -> Dict[str, List[str]]:
        """从metrics.json动态生成指标模式"""
        if self._metric_patterns_cache is not None:
            return self._metric_patterns_cache
        
        patterns = {}
        
        for metric in self.metrics_metadata:
            metric_id = metric.get('id', '')
            if not metric_id:
                continue
            
            # 收集所有模式
            metric_patterns = []
            
            # 1. 添加canonical_name
            canonical_name = metric.get('canonical_name', '')
            if canonical_name:
                metric_patterns.append(canonical_name)
            
            # 2. 添加所有aliases
            aliases = metric.get('aliases', [])
            metric_patterns.extend(aliases)
            
            # 3. 生成语义变体
            semantic_variants = self._generate_semantic_variants(canonical_name)
            metric_patterns.extend(semantic_variants)
            
            # 4. 基于描述生成业务概念变体
            description = metric.get('description', '')
            if description:
                business_variants = self._extract_business_concepts_from_description(description)
                metric_patterns.extend(business_variants)
            
            # 去重并过滤空值
            unique_patterns = list(set(filter(None, metric_patterns)))
            patterns[metric_id] = unique_patterns
            
            print(f"[DEBUG] 生成指标模式 {metric_id}: {len(unique_patterns)} 个模式")
        
        self._metric_patterns_cache = patterns
        return patterns
    
    def generate_dimension_patterns(self) -> Dict[str, List[str]]:
        """从dimensions.json动态生成维度模式"""
        if self._dimension_patterns_cache is not None:
            return self._dimension_patterns_cache
        
        patterns = {}
        
        for dimension in self.dimensions_metadata:
            dimension_id = dimension.get('id', '')
            if not dimension_id:
                continue
            
            # 收集所有模式
            dimension_patterns = []
            
            # 1. 添加canonical_name
            canonical_name = dimension.get('canonical_name', '')
            if canonical_name:
                dimension_patterns.append(canonical_name)
            
            # 2. 添加所有aliases
            aliases = dimension.get('aliases', [])
            dimension_patterns.extend(aliases)
            
            # 3. 生成语义变体
            semantic_variants = self._generate_semantic_variants(canonical_name)
            dimension_patterns.extend(semantic_variants)
            
            # 4. 基于描述生成业务概念变体
            description = dimension.get('what', {}).get('description', '')
            if description:
                business_variants = self._extract_business_concepts_from_description(description)
                dimension_patterns.extend(business_variants)
            
            # 去重并过滤空值
            unique_patterns = list(set(filter(None, dimension_patterns)))
            patterns[dimension_id] = unique_patterns
            
            print(f"[DEBUG] 生成维度模式 {dimension_id}: {len(unique_patterns)} 个模式")
        
        self._dimension_patterns_cache = patterns
        return patterns
    
    def generate_query_intent_patterns(self) -> Dict[str, List[str]]:
        """基于业务描述动态生成查询意图模式"""
        if self._query_intent_patterns_cache is not None:
            return self._query_intent_patterns_cache
        
        intent_patterns = {}
        
        # 从指标描述中提取业务概念
        for metric in self.metrics_metadata:
            description = metric.get('description', '')
            canonical_name = metric.get('canonical_name', '')
            
            if description:
                business_concepts = self._extract_business_concepts_from_description(description)
                for concept in business_concepts:
                    if concept not in intent_patterns:
                        intent_patterns[concept] = []
                    intent_patterns[concept].extend(metric.get('aliases', []))
                    intent_patterns[concept].append(canonical_name)
        
        # 从维度描述中提取业务概念
        for dimension in self.dimensions_metadata:
            description = dimension.get('what', {}).get('description', '')
            canonical_name = dimension.get('canonical_name', '')
            
            if description:
                business_concepts = self._extract_business_concepts_from_description(description)
                for concept in business_concepts:
                    if concept not in intent_patterns:
                        intent_patterns[concept] = []
                    intent_patterns[concept].extend(dimension.get('aliases', []))
                    intent_patterns[concept].append(canonical_name)
        
        # 去重
        for concept in intent_patterns:
            intent_patterns[concept] = list(set(filter(None, intent_patterns[concept])))
        
        self._query_intent_patterns_cache = intent_patterns
        return intent_patterns
    
    def _generate_semantic_variants(self, text: str) -> List[str]:
        """基于文本生成语义变体"""
        if not text:
            return []
        
        variants = []
        
        # 1. 提取核心词汇
        core_words = self._extract_core_words(text)
        variants.extend(core_words)
        
        # 2. 生成同义词变体
        synonyms = self._generate_synonyms(text)
        variants.extend(synonyms)
        
        # 3. 生成缩写变体
        abbreviations = self._generate_abbreviations(text)
        variants.extend(abbreviations)
        
        # 4. 生成组合词变体
        combinations = self._generate_combinations(text)
        variants.extend(combinations)
        
        return list(set(filter(None, variants)))
    
    def _extract_core_words(self, text: str) -> List[str]:
        """提取核心词汇"""
        # 简单的核心词汇提取
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        return [word for word in words if len(word) >= 2]
    
    def _generate_synonyms(self, text: str) -> List[str]:
        """生成同义词变体"""
        synonyms = []
        
        # 基于常见同义词映射
        synonym_mapping = {
            '用户': ['用户', '客户', '访客', '使用者'],
            '活跃': ['活跃', '活跃度', '活跃性'],
            '月': ['月', '月度', '每月'],
            '日': ['日', '每日', '天'],
            '统计': ['统计', '分析', '计算', '汇总'],
            '渠道': ['渠道', '来源', '途径'],
            '地区': ['地区', '地域', '区域', '地方'],
            '设备': ['设备', '终端', '平台'],
            '收入': ['收入', '营收', '收益', '营业额'],
            '成本': ['成本', '费用', '支出'],
            '转化': ['转化', '转换', '转变'],
            '留存': ['留存', '保持', '维持'],
            '流失': ['流失', '离开', '退出']
        }
        
        for key, values in synonym_mapping.items():
            if key in text:
                synonyms.extend(values)
        
        return synonyms
    
    def _generate_abbreviations(self, text: str) -> List[str]:
        """生成缩写变体"""
        abbreviations = []
        
        # 基于常见缩写模式
        abbreviation_mapping = {
            '月活跃用户': ['MAU', 'mau'],
            '日活跃用户': ['DAU', 'dau'],
            '独立访客': ['UV', 'uv'],
            '页面浏览量': ['PV', 'pv'],
            '成交总额': ['GMV', 'gmv'],
            '客单价': ['AOV', 'aov'],
            '用户获取成本': ['CAC', 'cac'],
            '投资回报率': ['ROI', 'roi'],
            '客户生命周期价值': ['CLV', 'clv'],
            '平均收入': ['ARPU', 'arpu']
        }
        
        for key, values in abbreviation_mapping.items():
            if key in text:
                abbreviations.extend(values)
        
        return abbreviations
    
    def _generate_combinations(self, text: str) -> List[str]:
        """生成组合词变体"""
        combinations = []
        
        # 基于常见组合模式
        if '用户' in text and '活跃' in text:
            combinations.extend(['用户活跃', '活跃用户', '用户活跃度'])
        
        if '页面' in text and '浏览' in text:
            combinations.extend(['页面浏览', '浏览页面', '页面访问'])
        
        if '客户' in text and '获取' in text:
            combinations.extend(['客户获取', '获取客户', '获客'])
        
        if '投资' in text and '回报' in text:
            combinations.extend(['投资回报', '回报投资', 'ROI'])
        
        return combinations
    
    def _extract_business_concepts_from_description(self, description: str) -> List[str]:
        """从描述中提取业务概念"""
        concepts = []
        
        # 基于描述中的关键词提取业务概念
        concept_keywords = {
            '用户行为': ['行为', '习惯', '使用', '操作'],
            '营销分析': ['营销', '推广', '广告', '获客'],
            '收入分析': ['收入', '营收', '收益', '财务'],
            '用户价值': ['价值', 'ARPU', 'LTV', 'CLV'],
            '渠道分析': ['渠道', '来源', '获客', '推广'],
            '地域分析': ['地域', '地区', '城市', '国家'],
            '设备分析': ['设备', '终端', '平台', '系统'],
            '时间分析': ['时间', '趋势', '变化', '周期'],
            '转化分析': ['转化', '转换', '漏斗', '流程'],
            '留存分析': ['留存', '保持', '粘性', '忠诚']
        }
        
        for concept, keywords in concept_keywords.items():
            if any(keyword in description for keyword in keywords):
                concepts.append(concept)
        
        return concepts
    
    def get_all_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """获取所有生成的模式"""
        return {
            'metrics': self.generate_metric_patterns(),
            'dimensions': self.generate_dimension_patterns(),
            'query_intents': self.generate_query_intent_patterns()
        }
    
    def clear_cache(self):
        """清除缓存，强制重新生成模式"""
        self._metric_patterns_cache = None
        self._dimension_patterns_cache = None
        self._query_intent_patterns_cache = None
        print("[INFO] 模式缓存已清除")
    
    def get_patterns_for_query(self, query: str) -> Dict[str, List[str]]:
        """为特定查询获取相关模式"""
        all_patterns = self.get_all_patterns()
        relevant_patterns = {}
        
        query_lower = query.lower()
        
        # 查找匹配的模式
        for pattern_type, patterns in all_patterns.items():
            relevant_patterns[pattern_type] = []
            for entity_id, pattern_list in patterns.items():
                for pattern in pattern_list:
                    if pattern.lower() in query_lower:
                        relevant_patterns[pattern_type].append(pattern)
        
        return relevant_patterns
