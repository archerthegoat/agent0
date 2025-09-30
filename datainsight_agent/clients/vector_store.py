from __future__ import annotations

from typing import List, Tuple, Optional
from pathlib import Path
import json

import hnswlib
import os
from datainsight_agent.config.settings import load_settings

try:
    from pymilvus import (connections as _milvus_conn, FieldSchema as _Field,
                          CollectionSchema as _Schema, DataType as _DT,
                          Collection as _Collection, utility as _mutil)
except Exception:
    _milvus_conn = None
    _Field = _Schema = _DT = _Collection = _mutil = None
try:
	from fastembed import TextEmbedding
except Exception:
	TextEmbedding = None  # optional


class LocalHNSWVectorStore:
	"""Local HNSW vector index backed by hnswlib."""

	def __init__(self, index_dir: Path, dim: int = 384, space: str = "ip") -> None:
		self.index_dir = Path(index_dir)
		self.index_dir.mkdir(parents=True, exist_ok=True)
		self.dim = dim
		self.space = space
		self._index_path = self.index_dir / "vectors.bin"
		self._meta_path = self.index_dir / "meta.jsonl"
		self._index = hnswlib.Index(space=self.space, dim=self.dim)
		self._initialized = False
		self._metas_cache: List[dict] = []
		if self._index_path.exists():
			self._index.load_index(str(self._index_path))
			self._initialized = True
			# set query-time ef if provided
			try:
				s = load_settings()
				ef = int(getattr(s, "retrieval_hnsw_ef", 64) or 64)
				self._index.set_ef(max(16, ef))
			except Exception:
				pass
		# preload metas once to avoid repeated file I/O
		self._preload_metas()

	def _preload_metas(self) -> None:
		self._metas_cache = []
		if self._meta_path.exists():
			with self._meta_path.open("r", encoding="utf-8") as f:
				for line in f:
					try:
						self._metas_cache.append(json.loads(line))
					except Exception:
						self._metas_cache.append({})

	def _ensure_capacity(self, num_new: int) -> None:
		if not self._initialized:
			initial_capacity = max(num_new, 64)
			self._index.init_index(max_elements=initial_capacity, ef_construction=200, M=16)
			self._initialized = True
			return
		current_count = self._index.get_current_count()
		max_elements = self._index.get_max_elements()
		needed = current_count + num_new
		if needed > max_elements:
			new_cap = max(needed, int(max_elements * 2))
			self._index.resize_index(new_cap)

	def add(self, ids: List[str], vectors: List[List[float]], metadatas: Optional[List[dict]] = None) -> None:
		if not ids:
			return
		self._ensure_capacity(len(ids))
		start = self._index.get_current_count()
		labels = list(range(start, start + len(ids)))
		self._index.add_items(vectors, labels)
		with self._meta_path.open("a", encoding="utf-8") as f:
			for i, _id in enumerate(ids):
				meta = metadatas[i] if (metadatas and i < len(metadatas)) else {"id": _id}
				if "id" not in meta:
					meta["id"] = _id
				f.write(json.dumps(meta, ensure_ascii=False) + "\n")
				# update in-memory cache
				self._metas_cache.append(meta)
		self._index.save_index(str(self._index_path))

	def search(self, query_vectors: List[List[float]], top_k: int = 5) -> List[List[Tuple[str, float]]]:
		if not self._initialized or self._index.get_current_count() == 0:
			return [[] for _ in query_vectors]
		# ensure ef each search (in case index reloaded elsewhere)
		try:
			s = load_settings()
			ef = int(getattr(s, "retrieval_hnsw_ef", 64) or 64)
			self._index.set_ef(max(16, ef))
		except Exception:
			pass
		labels, distances = self._index.knn_query(query_vectors, k=top_k)
		metas: List[dict] = self._metas_cache
		out: List[List[Tuple[str, float]]] = []
		for lbls, dists in zip(labels, distances):
			pairs: List[Tuple[str, float]] = []
			for lbl, dist in zip(lbls, dists):
				meta = metas[lbl] if 0 <= lbl < len(metas) else {"id": str(lbl)}
				pairs.append((str(meta.get("id", str(lbl))), float(dist)))
			out.append(pairs)
		return out


class MilvusVectorStore:
    """Milvus-backed vector store (minimal add/search).

    Env/Settings:
      - MILVUS_ENABLED (bool)
      - MILVUS_URI, MILVUS_DB, MILVUS_COLLECTION
      - VECTOR_DIM, VECTOR_SPACE (ip/l2)
    """

    def __init__(self, *, dim: int, space: str = "ip", collection: str | None = None) -> None:
        s = load_settings()
        if _milvus_conn is None:
            raise RuntimeError("pymilvus not installed")
        uri = getattr(s, "milvus_uri", "localhost:19530") or "localhost:19530"
        db = getattr(s, "milvus_db", "datainsight") or "datainsight"
        coll = collection or getattr(s, "milvus_collection", "kb_vectors") or "kb_vectors"

        self._dim = int(dim)
        self._metric = "IP" if str(space).lower() == "ip" else "L2"
        self._db = db
        self._coll_name = coll

        # connect with db_name when possible; support both grpc address and http uri
        try:
            _milvus_conn.disconnect("default")
        except Exception:
            pass
        try:
            # pymilvus accepts either address ("host:19530") or uri ("http://host:19531")
            conn_base: dict = {}
            if uri.startswith("http://") or uri.startswith("https://"):
                conn_base["uri"] = uri
            else:
                conn_base["address"] = uri
            user = getattr(s, "milvus_user", None) or ""
            password = getattr(s, "milvus_password", None) or ""
            if user or password:
                conn_base["user"] = user
                conn_base["password"] = password

            # First try connect with db_name
            try:
                _milvus_conn.connect(alias="default", db_name=db, **conn_base)
            except Exception as e1:
                msg = str(e1)
                # If database not found, connect to default, create it, then reconnect
                if "database not found" in msg or "database=" in msg:
                    try:
                        try:
                            _milvus_conn.disconnect("default")
                        except Exception:
                            pass
                        _milvus_conn.connect(alias="default", **conn_base)
                        try:
                            _mutil.create_database(db)
                        except Exception:
                            # If database creation unsupported, fall back to default DB
                            pass
                        try:
                            _milvus_conn.disconnect("default")
                        except Exception:
                            pass
                        # Try target DB again; if still failing, fall back to default DB without db_name
                        try:
                            _milvus_conn.connect(alias="default", db_name=db, **conn_base)
                        except Exception:
                            _milvus_conn.connect(alias="default", **conn_base)
                    except Exception as e2:
                        raise RuntimeError(f"Milvus connect/create database failed: {e2}")
                else:
                    raise RuntimeError(f"Milvus connect failed: {e1}")
        except Exception as e:
            raise RuntimeError(f"Milvus connect failed: {e}")

        # schema with metadata fields
        fs = [
            _Field(name="id", dtype=_DT.VARCHAR, max_length=128, is_primary=True, auto_id=False),
            _Field(name="vector", dtype=_DT.FLOAT_VECTOR, dim=self._dim),
            _Field(name="canonical_name", dtype=_DT.VARCHAR, max_length=256),
            _Field(name="aliases", dtype=_DT.VARCHAR, max_length=1024),
            _Field(name="type", dtype=_DT.VARCHAR, max_length=64),
        ]
        schema = _Schema(fields=fs, description="kb vectors")
        index_params = {"index_type": "HNSW", "metric_type": self._metric, "params": {"M": 16, "efConstruction": 200}}

        # create or get collection using ORM; do not swallow schema-missing errors
        try:
            if hasattr(_mutil, "has_collection") and _mutil.has_collection(coll, using="default"):
                self._c = _Collection(coll)
            else:
                self._c = _Collection(name=coll, schema=schema, using="default")
        except Exception as e:
            raise RuntimeError(f"Milvus create/get collection failed: {e}")
        # create index and load
        try:
            self._c.create_index(field_name="vector", index_params=index_params)
        except Exception as e:
            raise RuntimeError(f"Milvus create index failed: {e}")
        try:
            self._c.load()
        except Exception as e:
            raise RuntimeError(f"Milvus load collection failed: {e}")

    def add(self, ids: list[str], vectors: list[list[float]], metadatas: list[dict] | None = None) -> None:
        if not ids:
            return
        
        # 处理元数据
        canonical_names = []
        aliases_list = []
        types = []
        
        if metadatas:
            for meta in metadatas:
                canonical_names.append(meta.get("canonical_name", ""))
                aliases_list.append("|".join(meta.get("aliases", [])))
                types.append(meta.get("type", ""))
        else:
            canonical_names = [""] * len(ids)
            aliases_list = [""] * len(ids)
            types = [""] * len(ids)
        
        data = [ids, vectors, canonical_names, aliases_list, types]
        self._c.insert(data)
        self._c.flush()

    def search(self, query_vectors: list[list[float]], top_k: int = 5) -> list[list[tuple[str, float]]]:
        if not query_vectors:
            return [[]]
        params = {"metric_type": self._metric, "params": {"ef": 64}}
        
        # 获取所有字段名（除了 vector）
        output_fields = ["id", "canonical_name", "aliases", "type"]
        
        res = self._c.search(query_vectors, anns_field="vector", param=params, limit=top_k, output_fields=output_fields)
        out: list[list[tuple[str, float]]] = []
        for hits in res:
            pairs: list[tuple[str, float]] = []
            for h in hits:
                pairs.append((str(h.entity.get("id")), float(h.distance)))
            out.append(pairs)
        return out

    def get_metadata(self, entity_id: str) -> dict | None:
        """Get metadata for a specific entity by ID."""
        try:
            # 使用 query 方法获取特定 ID 的元数据
            res = self._c.query(
                expr=f'id == "{entity_id}"',
                output_fields=["id", "canonical_name", "aliases", "type"]
            )
            if res and len(res) > 0:
                return res[0]
        except Exception:
            pass
        return None


class EmbeddingModel:
	# 类级缓存，避免重复初始化
	_shared_instance = None
	_shared_backend = None
	_shared_emb = None
	_shared_openai_model = None
	
	def __new__(cls):
		# 单例模式，确保全局只有一个实例
		if cls._shared_instance is None:
			cls._shared_instance = super().__new__(cls)
		return cls._shared_instance
	
	def __init__(self) -> None:
		# 避免重复初始化
		if hasattr(self, '_initialized'):
			return
			
		s = load_settings()
		backend = (getattr(s, "embed_backend", "fastembed") or "fastembed").lower()
		
		# 检查是否已经初始化过相同配置
		if self._shared_backend == backend:
			self._backend = self._shared_backend
			if backend == "openai":
				self._openai_model = self._shared_openai_model
			else:
				self._emb = self._shared_emb
			self._initialized = True
			return
		
		# HuggingFace cache/mirror to mitigate SSL/mirror issues
		hf_cache = getattr(s, "hf_cache_dir", "./.hf_cache")
		os.environ.setdefault("HF_HOME", hf_cache)
		os.environ.setdefault("HF_DATASETS_CACHE", hf_cache)
		os.environ.setdefault("TRANSFORMERS_CACHE", hf_cache)
		hf_ep = (getattr(s, "hf_endpoint", "") or "").strip()
		if hf_ep:
			os.environ["HF_ENDPOINT"] = hf_ep
			os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
		fe_threads = int(getattr(s, "fastembed_threads", 0) or 0)
		if fe_threads > 0:
			os.environ["OMP_NUM_THREADS"] = str(fe_threads)
			os.environ["OPENBLAS_NUM_THREADS"] = str(fe_threads)

		if backend == "openai":
			# Use OpenAI-compatible embedding as fallback/backend
			self._backend = "openai"
			self._openai_model = getattr(s, "openai_embed_model", s.default_models.get("openai_embed_model", "text-embedding-3-small"))
			# 缓存OpenAI配置
			self._shared_backend = backend
			self._shared_openai_model = self._openai_model
		else:
			model_name = getattr(s, "embed_model_name", s.default_models.get("embed_model", "BAAI/bge-small-zh-v1.5"))
			if TextEmbedding is None:
				raise RuntimeError("fastembed is not available; set EMBED_BACKEND=openai or install fastembed")
			
			# 检查模型是否已经缓存
			try:
				# 尝试使用local_files_only=True来避免网络下载
				self._emb = TextEmbedding(model_name, local_files_only=True)
				self._backend = "fastembed"
				print(f"[INFO] 使用缓存的嵌入模型: {model_name}")
			except Exception:
				# 如果本地缓存不存在，则下载模型
				try:
					print(f"[INFO] 下载嵌入模型: {model_name}")
					self._emb = TextEmbedding(model_name)
					self._backend = "fastembed"
					print(f"[INFO] 嵌入模型下载完成: {model_name}")
				except Exception:
					# Fallback to OpenAI backend if fastembed download fails
					print(f"[WARN] fastembed模型下载失败，回退到OpenAI后端")
					self._backend = "openai"
					self._openai_model = getattr(s, "openai_embed_model", s.default_models.get("openai_embed_model", "text-embedding-3-small"))
					# 缓存OpenAI配置
					self._shared_backend = "openai"
					self._shared_openai_model = self._openai_model
					return
			
			# 缓存fastembed实例
			self._shared_backend = backend
			self._shared_emb = self._emb
		
		self._initialized = True

	def embed(self, texts: List[str]) -> List[List[float]]:
		if getattr(self, "_backend", "fastembed") == "openai":
			try:
				from openai import OpenAI
				api_key = os.getenv("OPENAI_API_KEY")
				# 使用配置化的API端点
				from datainsight_agent.config.settings import load_settings
				s = load_settings()
				base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or s.api_endpoints.get("openai", "https://api.openai.com/v1")
				client = OpenAI(api_key=api_key, base_url=base_url)
				out = client.embeddings.create(model=self._openai_model, input=texts)
				return [d.embedding for d in out.data]
			except Exception:
				# Last resort: zero vectors to keep pipeline alive (match index dim)
				from datainsight_agent.config.settings import load_settings as _ls
				dim = int(getattr(_ls(), "vector_dim", 384) or 384)
				return [[0.0] * dim for _ in texts]
		# fastembed path
		return list(self._emb.embed(texts))


