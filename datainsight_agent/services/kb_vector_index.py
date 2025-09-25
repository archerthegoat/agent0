from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from datainsight_agent.models.kb import KBEntity
from datainsight_agent.clients.vector_store import LocalHNSWVectorStore, EmbeddingModel
from datainsight_agent.config.settings import load_settings
try:
    from datainsight_agent.clients.vector_store import MilvusVectorStore
except Exception:
    MilvusVectorStore = None
from datainsight_agent.services.metric_registry import MetricRegistry
from datainsight_agent.services.auth import KnowledgeBaseAuth


@dataclass
class KBIndexItem:
    """KB索引项，包含实体信息和向量表示"""
    entity_id: str
    entity_type: str  # dimension, metric, mapping
    canonical_name: str
    aliases: List[str]
    description: str
    metadata: Dict[str, Any]
    text_content: str  # 用于向量化的完整文本


class KBVectorIndexBuilder:
    """KB向量索引构建器，预计算KB实体的向量表示"""
    
    def __init__(self, metadata_dir: str | Path = "metadata", index_dir: str | Path = "kb_vector_index"):
        self._metadata_dir = Path(metadata_dir)
        self._index_dir = Path(index_dir)
        self._embedder = EmbeddingModel()
        self._vector_store: object | None = None
        
    def build_index(self) -> int:
        """构建KB向量索引，返回索引的实体数量"""
        print(f"[INFO] 开始构建KB向量索引...")
        
        # 1. 收集所有KB实体
        kb_items = self._collect_kb_entities()
        print(f"[INFO] 收集到 {len(kb_items)} 个KB实体")
        
        if not kb_items:
            print("[WARN] 没有找到KB实体，跳过索引构建")
            return 0
        
        # 2. 生成向量表示
        texts = [item.text_content for item in kb_items]
        vectors = self._embedder.embed(texts)
        print(f"[INFO] 生成 {len(vectors)} 个向量表示")
        
        # 3. 构建向量索引
        self._index_dir.mkdir(parents=True, exist_ok=True)
        dim = len(vectors[0])
        s = load_settings()
        use_milvus = bool(getattr(s, "milvus_enabled", False)) and MilvusVectorStore is not None
        if use_milvus:
            self._vector_store = MilvusVectorStore(dim=dim, space=str(getattr(s, "vector_space", "ip")))
        else:
            self._vector_store = LocalHNSWVectorStore(index_dir=self._index_dir, dim=dim, space="ip")
        
        # 4. 存储向量和元数据
        ids = [item.entity_id for item in kb_items]
        metadatas = [self._item_to_metadata(item) for item in kb_items]
        
        self._vector_store.add(ids=ids, vectors=vectors, metadatas=metadatas)
        print(f"[INFO] KB向量索引构建完成，存储到 {self._index_dir}")
        
        return len(kb_items)
    
    def _resolve_metadata_path(self, key: str, default_name: str) -> Path:
        """根据 settings.metadata_files 与 metadata_dir 解析文件路径。

        - 若 settings 中给的是绝对路径，直接返回
        - 若以 "metadata/" 开头，则去掉前缀后与 self._metadata_dir 拼接
        - 否则将其视为在 metadata_dir 下的相对文件名
        """
        from datainsight_agent.config.settings import load_settings
        s = load_settings()
        raw = s.metadata_files.get(key, default_name)
        p = Path(raw)
        if p.is_absolute():
            return p
        parts = list(p.parts)
        if parts and parts[0].lower() == "metadata":
            return self._metadata_dir / Path(*parts[1:])
        return self._metadata_dir / p

    def _collect_kb_entities(self) -> List[KBIndexItem]:
        """收集所有KB实体"""
        items = []
        
        # 1. 收集维度/概念实体
        items.extend(self._collect_dimension_entities())
        
        # 2. 收集指标实体
        items.extend(self._collect_metric_entities())
        
        # 3. 收集映射实体
        items.extend(self._collect_mapping_entities())
        
        return items
    
    def _collect_dimension_entities(self) -> List[KBIndexItem]:
        """收集维度/概念实体"""
        items = []
        try:
            if not self._metadata_dir.exists():
                return items
                
            # 使用配置化的文件路径（兼容 settings 中含 "metadata/" 前缀的情况）
            dimensions_file = self._resolve_metadata_path("dimensions", "dimensions.json")
            if not dimensions_file.exists():
                return items
                
            obj = json.loads(dimensions_file.read_text(encoding="utf-8"))
            arr = obj if isinstance(obj, list) else [obj]
            
            for it in arr:
                try:
                    entity = KBEntity(**it)
                    entity_type = getattr(entity, "type", "").lower()
                    
                    # 只处理维度/概念类型
                    if entity_type in {"dimension", "concept", ""}:
                        # 构建文本内容
                        texts = [entity.canonical_name] + list(entity.aliases)
                        if entity.what and entity.what.description:
                            texts.append(entity.what.description)
                        
                        text_content = " ".join(texts)
                        
                        item = KBIndexItem(
                            entity_id=f"dim_{entity.canonical_name}",
                            entity_type="dimension",
                            canonical_name=entity.canonical_name,
                            aliases=list(entity.aliases),
                            description=entity.what.description if entity.what else "",
                            metadata={
                                "column": entity.how.data_source.column if entity.how and entity.how.data_source else None,
                                "file": dimensions_file.name
                            },
                            text_content=text_content
                        )
                        items.append(item)
                except Exception as e:
                    print(f"[WARN] 跳过无效的维度实体: {e}")
                    continue
        except Exception as e:
            print(f"[ERROR] 收集维度实体失败: {e}")
        
        return items
    
    def _collect_metric_entities(self) -> List[KBIndexItem]:
        """收集指标实体"""
        items = []
        try:
            # 使用配置化的文件路径（兼容 settings 中含 "metadata/" 前缀的情况）
            metrics_file = self._resolve_metadata_path("metrics", "metrics.json")
            if not metrics_file.exists():
                return items
                
            obj = json.loads(metrics_file.read_text(encoding="utf-8"))
            arr = obj if isinstance(obj, list) else [obj]
            
            for it in arr:
                try:
                    entity = KBEntity(**it)
                    entity_type = getattr(entity, "type", "").lower()
                    
                    # 只处理指标类型
                    if entity_type == "metric":
                        # 构建文本内容
                        texts = [entity.canonical_name] + list(entity.aliases)
                        text_content = " ".join(texts)
                        
                        item = KBIndexItem(
                            entity_id=f"metric_{entity.id}",
                            entity_type="metric",
                            canonical_name=entity.canonical_name,
                            aliases=list(entity.aliases),
                            description="",
                            metadata={
                                "metric_id": entity.id,
                                "file": metrics_file.name
                            },
                            text_content=text_content
                        )
                        items.append(item)
                except Exception as e:
                    print(f"[WARN] 跳过无效的指标实体: {e}")
                    continue
        except Exception as e:
            print(f"[ERROR] 收集指标实体失败: {e}")
        
        return items
    
    def _collect_mapping_entities(self) -> List[KBIndexItem]:
        """收集映射实体"""
        items = []
        try:
            # 使用配置化的文件路径（兼容 settings 中含 "metadata/" 前缀的情况）
            mapping_file = self._resolve_metadata_path("intent_mappings", "intent_mappings.json")
            if not mapping_file.exists():
                return items
            
            obj = json.loads(mapping_file.read_text(encoding="utf-8"))
            mappings = obj.get("group_by", []) if isinstance(obj, dict) else []
            
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    continue
                
                phrases = mapping.get("phrases", [])
                column = mapping.get("column", "")
                
                if phrases and column:
                    text_content = f"{' '.join(phrases)} {column}"
                    
                    item = KBIndexItem(
                        entity_id=f"mapping_{column}",
                        entity_type="mapping",
                        canonical_name=column,
                        aliases=phrases,
                        description="",
                        metadata={
                            "column": column,
                            "phrases": phrases
                        },
                        text_content=text_content
                    )
                    items.append(item)
        except Exception as e:
            print(f"[ERROR] 收集映射实体失败: {e}")
        
        return items
    
    def _item_to_metadata(self, item: KBIndexItem) -> Dict[str, Any]:
        """将KBIndexItem转换为向量存储的元数据"""
        return {
            "entity_id": item.entity_id,
            "entity_type": item.entity_type,
            "canonical_name": item.canonical_name,
            "aliases": item.aliases,
            "description": item.description,
            **item.metadata
        }


class KBVectorRetriever:
    """基于向量索引的KB检索器"""
    
    def __init__(self, index_dir: str | Path = "kb_vector_index"):
        self._index_dir = Path(index_dir)
        self._embedder = EmbeddingModel()
        self._vector_store: object | None = None
        self._auth = KnowledgeBaseAuth()  # 添加权限验证
        self._load_index()
    
    def _load_index(self):
        """加载向量索引"""
        try:
            if not self._index_dir.exists():
                print(f"[WARN] KB向量索引不存在: {self._index_dir}")
                return
            
            # 优化：缓存向量维度，避免重复计算
            if not hasattr(self, '_cached_dim'):
                self._cached_dim = len(self._embedder.embed(["__probe__"])[0])
            
            s = load_settings()
            use_milvus = bool(getattr(s, "milvus_enabled", False)) and MilvusVectorStore is not None
            if use_milvus:
                self._vector_store = MilvusVectorStore(dim=self._cached_dim, space=str(getattr(s, "vector_space", "ip")))
            else:
                self._vector_store = LocalHNSWVectorStore(index_dir=self._index_dir, dim=self._cached_dim, space="ip")
            print(f"[INFO] KB向量索引加载成功: {self._index_dir}")
        except Exception as e:
            print(f"[ERROR] 加载KB向量索引失败: {e}")
    
    def search(self, query: str, top_k: int = 5, entity_types: List[str] = None, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """基于向量相似性搜索KB实体"""
        # 权限检查
        if not self._auth.check_permission(user_id, "kb_search", "read"):
            print(f"[WARN] 用户 {user_id} 没有知识库搜索权限")
            return []
            
        if not self._vector_store:
            return []
        
        try:
            # 生成查询向量
            query_vector = self._embedder.embed([query])[0]
            
            # 向量搜索
            results = self._vector_store.search([query_vector], top_k=top_k)[0]
            
            # 过滤和格式化结果
            filtered_results = []
            for entity_id, score in results:
                metadata = self._get_entity_metadata(entity_id)
                if not metadata:
                    continue
                
                # 按实体类型过滤
                if entity_types and metadata.get("entity_type") not in entity_types:
                    continue
                
                filtered_results.append({
                    "entity_id": entity_id,
                    "score": float(score),
                    "metadata": metadata
                })
            
            return filtered_results
        except Exception as e:
            print(f"[ERROR] KB向量搜索失败: {e}")
            return []
    
    def _get_entity_metadata(self, entity_id: str) -> Dict[str, Any] | None:
        """获取实体元数据"""
        try:
            # 从向量存储中获取元数据
            if hasattr(self._vector_store, 'get_metadata'):
                metadata = self._vector_store.get_metadata(entity_id)
                if metadata:
                    return metadata
            
            # 如果向量存储没有元数据方法，尝试从构建的索引中查找
            # 这里我们需要在构建时保存元数据映射
            if hasattr(self, '_entity_metadata_map'):
                return self._entity_metadata_map.get(entity_id)
            
            # 简化实现，根据entity_id推断类型
            if entity_id.startswith('dim_'):
                return {
                    "entity_id": entity_id,
                    "entity_type": "dimension",
                    "canonical_name": entity_id.replace('dim_', '')
                }
            elif entity_id.startswith('metric_'):
                return {
                    "entity_id": entity_id,
                    "entity_type": "metric", 
                    "canonical_name": entity_id.replace('metric_', '')
                }
            elif entity_id.startswith('mapping_'):
                return {
                    "entity_id": entity_id,
                    "entity_type": "mapping",
                    "canonical_name": entity_id.replace('mapping_', '')
                }
            
            return {
                "entity_id": entity_id,
                "entity_type": "unknown"
            }
        except Exception as e:
            print(f"[ERROR] 获取实体元数据失败: {e}")
            return {
                "entity_id": entity_id,
                "entity_type": "unknown"
            }


def build_kb_vector_index(metadata_dir: str | Path = "metadata", index_dir: str | Path = "kb_vector_index") -> int:
    """构建KB向量索引的便捷函数"""
    builder = KBVectorIndexBuilder(metadata_dir, index_dir)
    return builder.build_index()


def search_kb_entities(query: str, top_k: int = 10, index_dir: str | Path = "kb_vector_index") -> List[Dict[str, Any]]:
    """搜索KB实体的便捷函数"""
    retriever = KBVectorRetriever(index_dir)
    return retriever.search(query, top_k)
