"""
元数据加载器

为新的RAG组件提供统一的元数据访问接口。
支持动态加载和缓存元数据。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MetricMetadata:
    """指标元数据"""
    id: str
    canonical_name: str
    aliases: List[str]
    description: Optional[str] = None
    business_meaning: Optional[str] = None
    aggregation: Optional[Dict[str, Any]] = None
    table_mapping: Optional[Dict[str, Any]] = None
    formula_human: Optional[str] = None


@dataclass
class DimensionMetadata:
    """维度元数据"""
    id: str
    canonical_name: str
    aliases: List[str]
    description: Optional[str] = None
    data_source: Optional[Dict[str, Any]] = None


@dataclass
class MappingMetadata:
    """映射元数据"""
    id: str
    canonical_name: str
    aliases: List[str]
    mappings: List[Dict[str, Any]]


class MetadataLoader:
    """统一的元数据加载器"""
    
    def __init__(self, metadata_dir: str | Path = "metadata"):
        self.metadata_dir = Path(metadata_dir)
        
        # 缓存
        self._metrics_cache: Optional[List[MetricMetadata]] = None
        self._dimensions_cache: Optional[List[DimensionMetadata]] = None
        self._mappings_cache: Optional[List[MappingMetadata]] = None
    
    def load_metrics(self) -> List[MetricMetadata]:
        """加载指标元数据"""
        if self._metrics_cache is not None:
            return self._metrics_cache
        
        try:
            metrics_file = self.metadata_dir / "metrics.json"
            if not metrics_file.exists():
                print(f"[WARN] 指标元数据文件不存在: {metrics_file}")
                return []
            
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metrics_data = data if isinstance(data, list) else [data]
            
            metrics = []
            for metric_data in metrics_data:
                metric = MetricMetadata(
                    id=metric_data.get('id', ''),
                    canonical_name=metric_data.get('canonical_name', ''),
                    aliases=metric_data.get('aliases', []),
                    description=metric_data.get('description'),
                    business_meaning=metric_data.get('business_meaning'),
                    aggregation=metric_data.get('aggregation'),
                    table_mapping=metric_data.get('table_mapping'),
                    formula_human=metric_data.get('formula_human')
                )
                metrics.append(metric)
            
            self._metrics_cache = metrics
            print(f"[INFO] 加载了 {len(metrics)} 个指标元数据")
            return metrics
            
        except Exception as e:
            print(f"[ERROR] 加载指标元数据失败: {e}")
            return []
    
    def load_dimensions(self) -> List[DimensionMetadata]:
        """加载维度元数据"""
        if self._dimensions_cache is not None:
            return self._dimensions_cache
        
        try:
            dimensions_file = self.metadata_dir / "dimensions.json"
            if not dimensions_file.exists():
                print(f"[WARN] 维度元数据文件不存在: {dimensions_file}")
                return []
            
            with open(dimensions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                dimensions_data = data if isinstance(data, list) else [data]
            
            dimensions = []
            for dimension_data in dimensions_data:
                what_info = dimension_data.get('what', {})
                how_info = dimension_data.get('how', {})
                
                dimension = DimensionMetadata(
                    id=dimension_data.get('id', ''),
                    canonical_name=dimension_data.get('canonical_name', ''),
                    aliases=dimension_data.get('aliases', []),
                    description=what_info.get('description'),
                    data_source=how_info.get('data_source')
                )
                dimensions.append(dimension)
            
            self._dimensions_cache = dimensions
            print(f"[INFO] 加载了 {len(dimensions)} 个维度元数据")
            return dimensions
            
        except Exception as e:
            print(f"[ERROR] 加载维度元数据失败: {e}")
            return []
    
    def load_mappings(self) -> List[MappingMetadata]:
        """加载映射元数据"""
        if self._mappings_cache is not None:
            return self._mappings_cache
        
        try:
            mappings_file = self.metadata_dir / "mappings.json"
            if not mappings_file.exists():
                print(f"[WARN] 映射元数据文件不存在: {mappings_file}")
                return []
            
            with open(mappings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                mappings_data = data if isinstance(data, list) else [data]
            
            mappings = []
            for mapping_data in mappings_data:
                mapping = MappingMetadata(
                    id=mapping_data.get('id', ''),
                    canonical_name=mapping_data.get('canonical_name', ''),
                    aliases=mapping_data.get('aliases', []),
                    mappings=mapping_data.get('mappings', [])
                )
                mappings.append(mapping)
            
            self._mappings_cache = mappings
            print(f"[INFO] 加载了 {len(mappings)} 个映射元数据")
            return mappings
            
        except Exception as e:
            print(f"[ERROR] 加载映射元数据失败: {e}")
            return []
    
    def get_metric_by_id(self, metric_id: str) -> Optional[MetricMetadata]:
        """根据ID获取指标元数据"""
        metrics = self.load_metrics()
        for metric in metrics:
            if metric.id == metric_id:
                return metric
        return None
    
    def get_dimension_by_id(self, dimension_id: str) -> Optional[DimensionMetadata]:
        """根据ID获取维度元数据"""
        dimensions = self.load_dimensions()
        for dimension in dimensions:
            if dimension.id == dimension_id:
                return dimension
        return None
    
    def get_mapping_by_id(self, mapping_id: str) -> Optional[MappingMetadata]:
        """根据ID获取映射元数据"""
        mappings = self.load_mappings()
        for mapping in mappings:
            if mapping.id == mapping_id:
                return mapping
        return None
    
    def search_metrics_by_alias(self, alias: str) -> List[MetricMetadata]:
        """根据别名搜索指标"""
        metrics = self.load_metrics()
        matching_metrics = []
        
        for metric in metrics:
            if alias.lower() in [a.lower() for a in metric.aliases]:
                matching_metrics.append(metric)
        
        return matching_metrics
    
    def search_dimensions_by_alias(self, alias: str) -> List[DimensionMetadata]:
        """根据别名搜索维度"""
        dimensions = self.load_dimensions()
        matching_dimensions = []
        
        for dimension in dimensions:
            if alias.lower() in [a.lower() for a in dimension.aliases]:
                matching_dimensions.append(dimension)
        
        return matching_dimensions
    
    def clear_cache(self):
        """清除缓存"""
        self._metrics_cache = None
        self._dimensions_cache = None
        self._mappings_cache = None
        print("[INFO] 元数据缓存已清除")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取元数据统计信息"""
        metrics = self.load_metrics()
        dimensions = self.load_dimensions()
        mappings = self.load_mappings()
        
        return {
            'metrics_count': len(metrics),
            'dimensions_count': len(dimensions),
            'mappings_count': len(mappings),
            'total_entities': len(metrics) + len(dimensions) + len(mappings),
            'metrics_with_descriptions': sum(1 for m in metrics if m.description),
            'dimensions_with_descriptions': sum(1 for d in dimensions if d.description),
            'metrics_with_table_mapping': sum(1 for m in metrics if m.table_mapping),
            'dimensions_with_data_source': sum(1 for d in dimensions if d.data_source)
        }
