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
from datainsight_agent.services.registry.metric_registry import MetricRegistry
from datainsight_agent.services.utils.auth import KnowledgeBaseAuth


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
        
        # 3. 构建向量索引 - 强制使用 Milvus
        self._index_dir.mkdir(parents=True, exist_ok=True)
        dim = len(vectors[0])
        s = load_settings()
        
        if MilvusVectorStore is None:
            raise RuntimeError("MilvusVectorStore not available. Please install pymilvus and ensure MILVUS_ENABLED=true")
        
        self._vector_store = MilvusVectorStore(dim=dim, space=str(getattr(s, "vector_space", "ip")))
        
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
                                "file": metrics_file.name,
                                "aggregation": it.get("aggregation", {})
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
            # intent_mappings.json已删除，使用默认映射
            mapping_file = None
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
            
            # 优先使用Milvus向量存储，确保使用最新的实体数据
            if getattr(s, "milvus_enabled", False) and MilvusVectorStore is not None:
                try:
                    self._vector_store = MilvusVectorStore(dim=self._cached_dim, space=str(getattr(s, "vector_space", "ip")))
                    print(f"[INFO] KB向量索引加载成功 (Milvus): {self._index_dir}")
                except Exception as milvus_error:
                    print(f"[WARN] Milvus向量存储加载失败: {milvus_error}")
                    # 回退到本地HNSW
                    try:
                        from datainsight_agent.clients.vector_store import LocalHNSWVectorStore
                        self._vector_store = LocalHNSWVectorStore(
                            index_dir=self._index_dir, 
                            dim=self._cached_dim, 
                            space=str(getattr(s, "vector_space", "ip"))
                        )
                        print(f"[INFO] KB向量索引加载成功 (LocalHNSW): {self._index_dir}")
                    except Exception as local_error:
                        print(f"[ERROR] 本地向量存储加载失败: {local_error}")
                        raise RuntimeError("Both Milvus and LocalHNSW vector stores failed to load")
            else:
                # 如果Milvus未启用，使用本地HNSW
                try:
                    from datainsight_agent.clients.vector_store import LocalHNSWVectorStore
                    self._vector_store = LocalHNSWVectorStore(
                        index_dir=self._index_dir, 
                        dim=self._cached_dim, 
                        space=str(getattr(s, "vector_space", "ip"))
                    )
                    print(f"[INFO] KB向量索引加载成功 (LocalHNSW): {self._index_dir}")
                except Exception as local_error:
                    print(f"[WARN] 本地向量存储加载失败: {local_error}")
                    # 回退到Milvus（如果可用）
                    if MilvusVectorStore is None:
                        raise RuntimeError("MilvusVectorStore not available. Please install pymilvus and ensure MILVUS_ENABLED=true")
                    
                    self._vector_store = MilvusVectorStore(dim=self._cached_dim, space=str(getattr(s, "vector_space", "ip")))
                    print(f"[INFO] KB向量索引加载成功 (Milvus): {self._index_dir}")
        except Exception as e:
            print(f"[ERROR] 加载KB向量索引失败: {e}")
    
    def search_topics_and_metrics(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """第一阶段：用向量索引找到相关的指标或topic（精确匹配 + 标准化alias）"""
        # 权限检查
        if not self._auth.check_permission("default_user", "kb_search", "read"):
            return []
            
        if not self._vector_store:
            return []
        
        try:
            # 1. 先尝试精确匹配
            exact_matches = self._exact_metric_match(query)
            
            # 2. 无论精确匹配是否成功，都进行向量搜索以增加类型多样性
            print(f"[INFO] 精确匹配找到 {len(exact_matches)} 个指标，继续向量搜索增加类型多样性")
            
            # 生成查询向量
            query_vector = self._embedder.embed([query])[0]
            
            # 增加检索数量，确保类型多样性
            search_k = max(top_k * 3, 15)  # 检索更多候选，提高类型覆盖
            results = self._vector_store.search([query_vector], top_k=search_k)[0]
            
            # 过滤出指标和维度，并标准化alias（动态相似度阈值）
            topics_and_metrics = []
            # 动态相似度阈值：根据查询类型和长度调整
            base_threshold = 0.35  # 降低基础阈值，提高召回率
            query_length_factor = min(0.05, len(query) * 0.01)  # 长查询稍微降低阈值
            min_similarity_threshold = base_threshold - query_length_factor
            
            # 按类型分组，确保类型多样性
            type_groups = {'metric': [], 'dimension': [], 'mapping': [], 'concept': []}
            
            # 首先添加精确匹配的结果
            for match in exact_matches:
                entity_type = match.get('entity_type', 'metric')
                if entity_type in type_groups:
                    type_groups[entity_type].append(match)
            
            # 然后添加向量搜索结果
            for entity_id, score in results:
                metadata = self._get_entity_metadata(entity_id)
                if not metadata:
                    continue

                # 严格相似度筛选
                if float(score) < min_similarity_threshold:
                    continue
                    
                entity_type = metadata.get('entity_type') or metadata.get('type', '')
                if entity_type in ['metric', 'dimension', 'mapping', 'concept']:
                    # 标准化指标名称
                    standardized_metadata = self._standardize_metric_metadata(metadata)
                    
                    fragment = {
                        "entity_id": entity_id,
                        "entity_type": entity_type,
                        "score": float(score),
                        "metadata": standardized_metadata
                    }
                    
                    # 避免重复添加（精确匹配已经添加的）
                    if not any(f.get('entity_id') == entity_id for f in type_groups[entity_type]):
                        type_groups[entity_type].append(fragment)
            
            # 强制类型多样性：确保至少包含不同类型的实体
            selected_types = set()
            
            # 首先选择指标类型（优先级最高）
            if 'metric' in type_groups and type_groups['metric']:
                type_groups['metric'].sort(key=lambda x: x['score'], reverse=True)
                topics_and_metrics.extend(type_groups['metric'][:3])
                selected_types.add('metric')
            
            # 强制选择维度类型（如果存在）
            if 'dimension' in type_groups and type_groups['dimension']:
                type_groups['dimension'].sort(key=lambda x: x['score'], reverse=True)
                topics_and_metrics.extend(type_groups['dimension'][:2])
                selected_types.add('dimension')
            else:
                # 如果没有找到维度，尝试降低阈值强制检索
                print(f"[DEBUG] 未找到维度实体，尝试降低阈值强制检索")
                fallback_threshold = max(0.35, min_similarity_threshold - 0.10)  # 动态回退阈值
                for entity_id, score in results:
                    if float(score) >= fallback_threshold:
                        metadata = self._get_entity_metadata(entity_id)
                        if metadata and metadata.get('entity_type') == 'dimension':
                            fragment = {
                                "entity_id": entity_id,
                                "entity_type": "dimension",
                                "score": float(score),
                                "metadata": metadata
                            }
                            topics_and_metrics.append(fragment)
                            selected_types.add('dimension')
                            print(f"[DEBUG] 强制添加维度实体: {entity_id}, 分数: {score}")
                            break
            
            # 强制选择映射类型（如果存在）
            if 'mapping' in type_groups and type_groups['mapping']:
                type_groups['mapping'].sort(key=lambda x: x['score'], reverse=True)
                topics_and_metrics.extend(type_groups['mapping'][:1])
                selected_types.add('mapping')
            else:
                # 如果没有找到映射，尝试降低阈值强制检索
                print(f"[DEBUG] 未找到映射实体，尝试降低阈值强制检索")
                fallback_threshold = max(0.35, min_similarity_threshold - 0.10)  # 动态回退阈值
                for entity_id, score in results:
                    if float(score) >= fallback_threshold:
                        metadata = self._get_entity_metadata(entity_id)
                        if metadata and metadata.get('entity_type') == 'mapping':
                            fragment = {
                                "entity_id": entity_id,
                                "entity_type": "mapping",
                                "score": float(score),
                                "metadata": metadata
                            }
                            topics_and_metrics.append(fragment)
                            selected_types.add('mapping')
                            print(f"[DEBUG] 强制添加映射实体: {entity_id}, 分数: {score}")
                            break
            
            # 强制选择概念类型（如果存在）
            if 'concept' in type_groups and type_groups['concept']:
                type_groups['concept'].sort(key=lambda x: x['score'], reverse=True)
                topics_and_metrics.extend(type_groups['concept'][:1])
                selected_types.add('concept')
            
            print(f"[DEBUG] 强制类型多样性 - 已选择类型: {selected_types}")
            print(f"[DEBUG] 强制类型多样性 - 总结果数: {len(topics_and_metrics)}")
            print(f"[DEBUG] 各类型组数量 - metric: {len(type_groups.get('metric', []))}, dimension: {len(type_groups.get('dimension', []))}, mapping: {len(type_groups.get('mapping', []))}, concept: {len(type_groups.get('concept', []))}")
            
            # 如果结果不足，补充其他类型的结果
            if len(topics_and_metrics) < top_k:
                all_fragments = []
                for fragments in type_groups.values():
                    all_fragments.extend(fragments)
                
                # 按分数排序，补充剩余位置
                all_fragments.sort(key=lambda x: x['score'], reverse=True)
                for fragment in all_fragments:
                    if fragment not in topics_and_metrics and len(topics_and_metrics) < top_k:
                        topics_and_metrics.append(fragment)
            
            # 3. 回退机制：如果向量搜索结果不足，使用关键词匹配
            if len(topics_and_metrics) < 2:
                print(f"[INFO] 向量搜索结果不足({len(topics_and_metrics)}个)，启用关键词回退机制")
                keyword_results = self._keyword_fallback_search(query)
                for result in keyword_results:
                    if not any(f.get('entity_id') == result.get('entity_id') for f in topics_and_metrics):
                        topics_and_metrics.append(result)
                        if len(topics_and_metrics) >= top_k:
                            break
            
            # 最终按分数排序
            topics_and_metrics.sort(key=lambda x: x['score'], reverse=True)
            print(f"[INFO] 最终检索到 {len(topics_and_metrics)} 个实体")
            return topics_and_metrics[:top_k]
        except Exception as e:
            # 避免编码问题，使用安全的错误处理
            try:
                print(f"[ERROR] 第一阶段向量检索失败: {str(e)}")
            except UnicodeError:
                print(f"[ERROR] 第一阶段向量检索失败: encoding error")
            return []
    
    def _keyword_fallback_search(self, query: str) -> List[Dict[str, Any]]:
        """关键词回退搜索：当向量搜索失败时使用"""
        try:
            from datainsight_agent.services.registry.metric_registry import MetricRegistry
            
            registry = MetricRegistry()
            registry.load()
            
            # 提取查询中的关键词
            keywords = self._extract_metric_keywords(query)
            fallback_results = []
            
            for keyword in keywords:
                # 尝试从指标注册表匹配
                metric_def = registry.resolve_from_signals([keyword])
                if metric_def:
                    fallback_results.append({
                        "entity_id": f"metric_{metric_def.metric_id}",
                        "entity_type": "metric",
                        "score": 0.6,  # 回退搜索给中等分数
                        "metadata": {
                            'canonical_name': metric_def.canonical_name,
                            'aliases': metric_def.aliases,
                            'aggregation': metric_def.aggregation,
                            'metric_id': metric_def.metric_id,
                            'standardized': True
                        }
                    })
            
            # 阶段2优化：如果指标匹配失败，尝试复合指标匹配
            if not fallback_results:
                # 复合指标匹配
                compound_metrics = {
                    'page_views_per_session': {
                        'patterns': ['页面浏览数/会话', '浏览数/会话', '每会话浏览数', '页面/会话'],
                        'aggregation': {'function': 'AVG', 'field': 'pages_per_session', 'alias': 'page_views_per_session'}
                    },
                    'avg_session_duration': {
                        'patterns': ['会话时长', '平均会话时长', '会话时间'],
                        'aggregation': {'function': 'AVG', 'field': 'session_duration_minutes', 'alias': 'avg_session_duration'}
                    },
                    'customer_satisfaction': {
                        'patterns': ['满意度', '客户满意度', '满意度评分'],
                        'aggregation': {'function': 'AVG', 'field': 'satisfaction_score', 'alias': 'customer_satisfaction'}
                    },
                    'app_crash_rate': {
                        'patterns': ['崩溃率', 'APP崩溃率', '应用崩溃率'],
                        'aggregation': {'function': 'AVG', 'field': 'bounce_flag', 'alias': 'app_crash_rate'}
                    },
                    'cac': {
                        'patterns': ['获取成本', '客户获取成本', '获客成本'],
                        'aggregation': {'function': 'AVG', 'field': 'roi_ratio', 'alias': 'cac'}
                    }
                }
                
                for metric_name, config in compound_metrics.items():
                    for pattern in config['patterns']:
                        if pattern in query:
                            fallback_results.append({
                                "entity_id": f"metric_{metric_name}",
                                "entity_type": "metric",
                                "score": 0.7,  # 复合指标给较高分数
                                "metadata": {
                                    'canonical_name': metric_name,
                                    'aliases': [metric_name],
                                    'aggregation': config['aggregation'],
                                    'standardized': True
                                }
                            })
                            break
                    if fallback_results:
                        break
            
            # 如果复合指标匹配也失败，尝试维度匹配
            if not fallback_results:
                dimension_keywords = ['渠道', '地区', '设备', '平台', 'channel', 'region', 'device', 'platform']
                for keyword in dimension_keywords:
                    if keyword in query:
                        fallback_results.append({
                            "entity_id": f"dimension_{keyword}",
                            "entity_type": "dimension", 
                            "score": 0.5,
                            "metadata": {
                                'canonical_name': keyword,
                                'aliases': [keyword],
                                'standardized': True
                            }
                        })
                        break
            
            print(f"[INFO] 关键词回退搜索找到 {len(fallback_results)} 个结果")
            return fallback_results
            
        except Exception as e:
            print(f"[ERROR] 关键词回退搜索失败: {e}")
            return []
    
    def _exact_metric_match(self, query: str) -> List[Dict[str, Any]]:
        """精确匹配指标"""
        try:
            from datainsight_agent.services.registry.metric_registry import MetricRegistry
            
            registry = MetricRegistry()
            registry.load()
            
            # 提取查询中的指标关键词
            keywords = self._extract_metric_keywords(query)
            
            exact_matches = []
            for keyword in keywords:
                metric_def = registry.resolve_from_signals([keyword])
                if metric_def:
                    # 构造标准化的RAG片段
                    exact_matches.append({
                        "entity_id": f"metric_{metric_def.metric_id}",
                        "entity_type": "metric",
                        "score": 1.0,  # 精确匹配给最高分
                        "metadata": {
                            'canonical_name': metric_def.canonical_name,
                            'aliases': metric_def.aliases,
                            'aggregation': metric_def.aggregation,
                            'metric_id': metric_def.metric_id,
                            'standardized': True
                        }
                    })
            
            return exact_matches
        except Exception as e:
            # 避免编码问题，使用安全的错误处理
            try:
                print(f"[ERROR] 精确匹配失败: {str(e)}")
            except UnicodeError:
                print(f"[ERROR] 精确匹配失败: encoding error")
            return []
    
    def _extract_metric_keywords(self, query: str) -> List[str]:
        """从查询中提取指标关键词，使用METRIC_KEYWORDS映射（阶段2优化版）"""
        try:
            keywords = []
            query_lower = query.lower()
            
            # 使用METRIC_KEYWORDS映射而不是硬编码
            from datainsight_agent.config.keyword_mappings import METRIC_KEYWORDS
            
            # 1. 遍历METRIC_KEYWORDS，查找匹配的关键词
            for keyword, metric_alias in METRIC_KEYWORDS.items():
                try:
                    if keyword in query or keyword.lower() in query_lower:
                        keywords.append(keyword)
                        keywords.append(metric_alias)  # 同时添加标准别名
                except UnicodeError:
                    # 跳过有编码问题的关键词
                    continue
            
            # 2. 英文缩写匹配（增强版）
            import re
            try:
                # 匹配2-4个字母的缩写
                abbreviations = re.findall(r'\b[A-Z]{2,4}\b', query)
                keywords.extend(abbreviations)
                
                # 匹配小写缩写
                lowercase_abbr = re.findall(r'\b[a-z]{2,4}\b', query_lower)
                keywords.extend(lowercase_abbr)
            except Exception:
                pass
            
            # 3. 阶段2优化：上下文语义匹配
            context_patterns = {
                # ARPU相关上下文
                'arpu': ['用户价值', '平均收入', '人均收入', '用户平均收入'],
                # 页面浏览相关上下文
                'page_views_per_session': ['页面浏览', '浏览数', '每会话', '页面/会话'],
                # 会话时长相关上下文
                'avg_session_duration': ['会话时长', '会话时间', '平均时长'],
                # 满意度相关上下文
                'customer_satisfaction': ['满意度', '评分', '客户满意'],
                # 崩溃率相关上下文
                'app_crash_rate': ['崩溃', '崩溃率', '应用崩溃'],
                # 获取成本相关上下文
                'cac': ['获取成本', '获客成本', '客户获取'],
            }
            
            for metric, patterns in context_patterns.items():
                for pattern in patterns:
                    if pattern in query:
                        keywords.append(pattern)
                        keywords.append(metric)
                        break
            
            # 4. 复合指标识别（阶段2新增）
            compound_patterns = {
                'page_views_per_session': [
                    r'页面浏览数/会话',
                    r'浏览数/会话', 
                    r'每会话浏览数',
                    r'页面/会话'
                ],
                'avg_session_duration': [
                    r'会话时长',
                    r'平均会话时长',
                    r'会话时间'
                ]
            }
            
            for metric, patterns in compound_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, query):
                        keywords.append(metric)
                        break
            
            # 5. 去重并返回
            unique_keywords = list(set(keywords))
            print(f"[DEBUG] 提取的关键词: {unique_keywords}")
            return unique_keywords
            
        except Exception as e:
            print(f"[ERROR] 关键词提取失败: {e}")
            return []
    
    def _standardize_metric_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """标准化指标元数据，将alias映射到标准指标名称"""
        try:
            entity_type = metadata.get('entity_type', '')
            
            if entity_type == 'metric':
                # 使用MetricRegistry进行标准化
                from datainsight_agent.services.registry.metric_registry import MetricRegistry
                
                registry = MetricRegistry()
                registry.load()  # 确保加载指标定义
                canonical_name = metadata.get('canonical_name', '')
                aliases = metadata.get('aliases', [])
                
                # 尝试通过canonical_name或aliases找到标准定义
                metric_def = None
                if canonical_name:
                    metric_def = registry.resolve_from_signals([canonical_name])
                
                if not metric_def and aliases:
                    metric_def = registry.resolve_from_signals(aliases)
                
                if metric_def:
                    # 使用标准定义更新metadata
                    standardized_metadata = metadata.copy()
                    standardized_metadata.update({
                        'canonical_name': metric_def.canonical_name,
                        'aliases': metric_def.aliases,
                        'aggregation': metric_def.aggregation,
                        'metric_id': metric_def.metric_id,
                        'table_mapping': metric_def.table_mapping,  # 添加表映射信息
                        'standardized': True  # 标记已标准化
                    })
                    return standardized_metadata
            
            return metadata
        except Exception as e:
            # 避免编码问题，使用安全的错误处理
            try:
                print(f"[ERROR] 标准化指标元数据失败: {str(e)}")
            except UnicodeError:
                print(f"[ERROR] 标准化指标元数据失败: encoding error")
            return metadata
    
    def _get_entity_metadata(self, entity_id: str) -> Dict[str, Any] | None:
        """获取实体元数据"""
        try:
            # 从向量存储中获取元数据
            if hasattr(self._vector_store, 'get_metadata'):
                metadata = self._vector_store.get_metadata(entity_id)
                if metadata:
                    return metadata
            
            # 如果向量存储没有元数据方法，从原始 metadata 文件中查找
            if entity_id.startswith('metric_'):
                metric_id = entity_id.replace('metric_', '')
                # 从 metrics.json 中查找
                metrics_file = Path("metadata/metrics.json")
                if metrics_file.exists():
                    obj = json.loads(metrics_file.read_text(encoding="utf-8"))
                    arr = obj if isinstance(obj, list) else [obj]
                    for item in arr:
                        # 尝试匹配 id 或 canonical_name
                        if item.get("id") == metric_id or item.get("id") == entity_id:
                            return {
                                "entity_id": entity_id,
                                "entity_type": "metric",
                                "canonical_name": item.get("canonical_name", metric_id),
                                "aliases": item.get("aliases", []),
                                "metric_id": metric_id,
                                "file": "metrics.json",
                                "aggregation": item.get("aggregation", {})
                            }
            elif entity_id.startswith('dim_'):
                dim_id = entity_id.replace('dim_', '')
                # 从 dimensions.json 中查找
                dimensions_file = Path("metadata/dimensions.json")
                if dimensions_file.exists():
                    obj = json.loads(dimensions_file.read_text(encoding="utf-8"))
                    arr = obj if isinstance(obj, list) else [obj]
                    for item in arr:
                        if item.get("id") == entity_id or item.get("id") == dim_id:
                            return {
                                "entity_id": entity_id,
                                "entity_type": "dimension",
                                "canonical_name": item.get("canonical_name", dim_id),
                                "aliases": item.get("aliases", []),
                                "column": item.get("how", {}).get("data_source", {}).get("column"),
                                "file": "dimensions.json"
                            }
            elif entity_id.startswith('mapping_'):
                mapping_id = entity_id.replace('mapping_', '')
                # 从 mappings.json 中查找
                mappings_file = Path("metadata/mappings.json")
                if mappings_file.exists():
                    obj = json.loads(mappings_file.read_text(encoding="utf-8"))
                    arr = obj if isinstance(obj, list) else [obj]
                    for item in arr:
                        if item.get("id") == entity_id or item.get("id") == mapping_id:
                            return {
                                "entity_id": entity_id,
                                "entity_type": "mapping",
                                "canonical_name": item.get("canonical_name", mapping_id),
                                "aliases": item.get("aliases", []),
                                "mappings": item.get("mappings", []),
                                "file": "mappings.json"
                            }
            
            # 最后的回退：根据entity_id推断类型
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
            # 避免编码问题，使用安全的错误处理
            try:
                print(f"[ERROR] 获取实体元数据失败: {str(e)}")
            except UnicodeError:
                print(f"[ERROR] 获取实体元数据失败: encoding error")
            return {
                "entity_id": entity_id,
                "entity_type": "unknown"
            }
    
    def find_related_entities(self, topics_and_metrics: List[Dict[str, Any]]) -> List[str]:
        """第二阶段：根据图结构找到连接的关系片段"""
        related_entities = set()
        
        for item in topics_and_metrics:
            entity_id = item['entity_id']
            # 兼容精确匹配和向量搜索的结果结构
            entity_type = item.get('entity_type') or item['metadata'].get('entity_type')
            
            if entity_type == 'metric':
                # 指标相关的维度：从intent_mappings中找到相关分组字段
                related_entities.update(self._find_metric_related_dimensions(entity_id))
                
            elif entity_type == 'dimension':
                # 维度相关的指标：找到使用这个维度的指标
                related_entities.update(self._find_dimension_related_metrics(entity_id))
        
        return list(related_entities)
    
    def _find_metric_related_dimensions(self, metric_id: str) -> List[str]:
        """找到与指标相关的维度"""
        related_dimensions = []
        
        # intent_mappings.json已删除，使用默认分组维度
        group_by_mappings = [
            {"concept": "渠道", "field": "channel"},
            {"concept": "平台", "field": "platform"},
            {"concept": "地区", "field": "region"},
            {"concept": "设备", "field": "device_type"},
            {"concept": "用户等级", "field": "user_level"}
        ]
        
        for mapping in group_by_mappings:
            column = mapping.get('column', '')
            if column:
                # 找到对应的维度实体
                dimension_entity = self._find_dimension_by_column(column)
                if dimension_entity:
                    related_dimensions.append(dimension_entity)
        
        return related_dimensions
    
    def _find_dimension_related_metrics(self, dimension_id: str) -> List[str]:
        """找到与维度相关的指标"""
        related_metrics = []
        
        # 找到所有可能使用这个维度的指标
        all_metrics = self._load_all_metrics()
        for metric in all_metrics:
            # 检查指标是否可能与这个维度相关
            if self._is_metric_dimension_related(metric, dimension_id):
                related_metrics.append(metric['id'])
        
        return related_metrics
    
    def _load_intent_mappings(self) -> Dict[str, Any]:
        """加载意图映射配置（已删除intent_mappings.json，返回默认配置）"""
        return {
            "group_by": [
                {"concept": "渠道", "field": "channel"},
                {"concept": "平台", "field": "platform"},
                {"concept": "地区", "field": "region"},
                {"concept": "设备", "field": "device_type"},
                {"concept": "用户等级", "field": "user_level"}
            ]
        }
    
    def _load_all_metrics(self) -> List[Dict[str, Any]]:
        """加载所有指标定义"""
        try:
            metrics_file = Path("metadata/metrics.json")
            if metrics_file.exists():
                return json.loads(metrics_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[ERROR] 加载指标定义失败: {e}")
        return []
    
    def _find_dimension_by_column(self, column: str) -> str:
        """根据列名找到对应的维度实体ID"""
        try:
            dimensions_file = Path("metadata/dimensions.json")
            if dimensions_file.exists():
                obj = json.loads(dimensions_file.read_text(encoding="utf-8"))
                arr = obj if isinstance(obj, list) else [obj]
                for item in arr:
                    data_source = item.get("how", {}).get("data_source", {})
                    if data_source.get("column") == column:
                        return f"dim_{item.get('canonical_name', '')}"
        except Exception as e:
            print(f"[ERROR] 查找维度失败: {e}")
        return ""
    
    def _is_metric_dimension_related(self, metric: Dict[str, Any], dimension_id: str) -> bool:
        """检查指标是否与维度相关"""
        # 简单的相关性检查：如果指标名称包含维度相关词汇
        metric_name = metric.get('canonical_name', '').lower()
        dimension_name = dimension_id.replace('dim_', '').lower()
        
        # 检查是否有共同的关键词
        common_keywords = ['用户', '活跃', '访问', '订单', '收入']
        for keyword in common_keywords:
            if keyword in metric_name and keyword in dimension_name:
                return True
        
        return False
    
    def search_with_graph_relations(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """三阶段RAG：向量检索 → 图关系 → 精准召回（优化权重）"""
        
        # 第一阶段：向量检索找指标/topic
        topics_and_metrics = self.search_topics_and_metrics(query, top_k=3)
        
        if not topics_and_metrics:
            print(f"[INFO] 第一阶段没有找到相关指标/topic")
            return []
        
        print(f"[INFO] 第一阶段找到 {len(topics_and_metrics)} 个相关指标/topic")
        
        # 第二阶段：图结构关系查找
        related_entities = self.find_related_entities(topics_and_metrics)
        
        print(f"[INFO] 第二阶段找到 {len(related_entities)} 个相关实体")
        
        # 第三阶段：基于关系的精准召回（优化权重）
        final_results = []
        
        # 添加原始找到的指标/topic（保持原始分数）
        for item in topics_and_metrics:
            final_results.append(item)
        
        # 添加通过关系找到的相关实体（差异化权重）
        for entity_id in related_entities:
            metadata = self._get_entity_metadata(entity_id)
            if metadata:
                entity_type = metadata.get('entity_type', '')
                
                # 根据实体类型分配不同权重
                if entity_type == 'metric':
                    # 指标实体：高权重
                    relation_score = 0.9
                elif entity_type == 'dimension':
                    # 维度实体：中等权重
                    relation_score = 0.6
                elif entity_type == 'mapping':
                    # 映射实体：低权重
                    relation_score = 0.4
                else:
                    # 其他实体：最低权重
                    relation_score = 0.3
                
                final_results.append({
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "score": relation_score,
                    "metadata": metadata,
                    "relation_source": "graph"
                })
        
        # 去重并按分数排序
        seen_entities = set()
        unique_results = []
        for result in final_results:
            entity_id = result['entity_id']
            if entity_id not in seen_entities:
                seen_entities.add(entity_id)
                unique_results.append(result)
        
        # 按分数排序（指标优先）
        unique_results.sort(key=lambda x: (x['score'], x.get('entity_type', '') == 'metric'), reverse=True)
        
        print(f"[INFO] 第三阶段最终召回 {len(unique_results)} 个实体")
        
        # 确保指标实体优先返回
        metric_results = [r for r in unique_results if r.get('entity_type') == 'metric']
        other_results = [r for r in unique_results if r.get('entity_type') != 'metric']
        
        # 重新排序：指标在前，其他在后
        final_sorted = metric_results + other_results
        
        return final_sorted[:top_k]
    


def build_kb_vector_index(metadata_dir: str | Path = "metadata", index_dir: str | Path = "kb_vector_index") -> int:
    """构建KB向量索引的便捷函数"""
    builder = KBVectorIndexBuilder(metadata_dir, index_dir)
    return builder.build_index()


def search_kb_entities(query: str, top_k: int = 10, index_dir: str | Path = "kb_vector_index") -> List[Dict[str, Any]]:
    """搜索KB实体的便捷函数"""
    retriever = KBVectorRetriever(index_dir)
    return retriever.search(query, top_k)
