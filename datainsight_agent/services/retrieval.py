from __future__ import annotations

from typing import List, Optional, Tuple, Dict

from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel
from datainsight_agent.clients.graph_client import LocalGraphClient
from datainsight_agent.models.kb import KBEntity
from datainsight_agent.config.settings import load_settings


class RetrievalService:
	"""Hybrid retrieval orchestrating local/remote stores with safe fallbacks.

	Current enabled backends:
	- Milvus vector index (when MILVUS_ENABLED=true)
	- Local SQLite graph (always available if built)
	- Placeholders for Elasticsearch/Neo4j (feature flags in settings)
	"""

	def __init__(self, vector_store: Optional[MilvusVectorStore] = None, local_graph: Optional[LocalGraphClient] = None) -> None:
		self.vector_store = vector_store
		self.local_graph = local_graph
		self._embedder = EmbeddingModel() if vector_store else None

	def recall_by_embedding(self, embedding: List[float], top_k: int = 5) -> List[KBEntity]:
		if not self.vector_store:
			return []
		results = self.vector_store.search([embedding], top_k=top_k)[0]
		if not results:
			return []
		
		entities: List[KBEntity] = []
		for rid, distance in results:
			try:
				# 从 Milvus 获取元数据
				metadata = self.vector_store.get_metadata(rid)
				if metadata:
					# 解析别名
					aliases = metadata.get("aliases", "").split("|") if metadata.get("aliases") else []
					aliases = [a for a in aliases if a]  # 过滤空字符串
					
					entity = KBEntity(
						id=rid,
						canonical_name=metadata.get("canonical_name", ""),
						aliases=aliases,
						type=metadata.get("type", "")
					)
					entities.append(entity)
			except Exception:
				continue
		return entities

	def hybrid_knowledge_retriever(self, concepts: List[str], top_k: int = 5) -> List[KBEntity]:
		"""Retrieve KB entities by concept names with two-stage retrieval (if enabled).

		Stage 1: lightweight graph/name filter by Q2Q concepts → candidate ids
		Stage 2: vector Top-K over concatenated concepts → map ids via graph, then
		         score fusion (vector + graph) with configurable weights.

		If ES/Neo4j feature flags are enabled in settings and corresponding
		clients are wired (future phases), the fusion can be extended transparently.
		"""
		if not concepts:
			return []
		s = load_settings()
		enabled = bool(getattr(s, "two_stage_retrieval_enabled", True))
		stage1_k = int(getattr(s, "retrieval_top_k_stage1", 12))
		w_vec = float(getattr(s, "retrieval_weight_vector", 0.7))
		w_g = float(getattr(s, "retrieval_weight_graph", 0.3))

		# Helper: normalize distance to score in [0,1], higher is better
		def _dist_to_score(dist: float, space: str) -> float:
			try:
				if (space or "ip").lower() == "ip":
					# Inner product: hnswlib returns higher is better, but some builds return distance;
					# we assume larger is better and clamp to [0,1]
					return max(0.0, min(1.0, float(dist)))
				# L2: smaller distance is better; map to (1 / (1 + d))
				d = float(dist)
				return 1.0 / (1.0 + max(0.0, d))
			except Exception:
				return 0.0

		# Stage 1: Graph/name filter to get candidate ids (cheap)
		candidate_ids: List[str] = []
		if enabled and self.local_graph:
			try:
				rows = self.local_graph.find_by_concepts(concepts, limit=stage1_k)
				candidate_ids = [str(r.get("id")) for r in rows if r.get("id")]
			except Exception as e:
				try:
					print(f"[DEBUG] Graph filter failed: {str(e)}")
				except UnicodeError:
					print(f"[DEBUG] Graph filter failed: encoding error")
				candidate_ids = []

		# Stage 2: Vector Top-K + graph expansion (with simple TTL cache on query vector)
		vec_pairs: List[Tuple[str, float]] = []  # (id, score)
		if self.vector_store and self._embedder:
			try:
				# Cache embedding for identical concept lists in single process
				from time import time as _now
				_cache_key = "\n".join(concepts)
				if not hasattr(self, "_embed_cache"):
					self._embed_cache = {}
				if not hasattr(self, "_embed_cache_ts"):
					self._embed_cache_ts = {}
				ttl = int(getattr(load_settings(), "retrieval_cache_ttl_seconds", 300) or 300)
				now_s = int(_now())
				qvec = None
				if _cache_key in self._embed_cache and (now_s - int(self._embed_cache_ts.get(_cache_key, 0))) < ttl:
					qvec = self._embed_cache[_cache_key]
				else:
					qvec = self._embedder.embed([_cache_key])[0]
					self._embed_cache[_cache_key] = qvec
					self._embed_cache_ts[_cache_key] = now_s
				# 减少over-fetch倍数，提高检索效率
				over = int(getattr(load_settings(), "retrieval_overfetch", 2) or 2)
				pairs = self.vector_store.search([qvec], top_k=max(top_k, top_k * over))[0]
				space = getattr(self.vector_store, "space", "ip")
				for _id, dist in pairs:
					vec_pairs.append((str(_id), _dist_to_score(dist, space)))
			except Exception as e:
				try:
					print(f"[DEBUG] Vector search failed: {str(e)}")
				except UnicodeError:
					print(f"[DEBUG] Vector search failed: encoding error")
				vec_pairs = []

		# Graph-only candidates get a small base score to participate
		graph_pairs: List[Tuple[str, float]] = []
		for cid in candidate_ids:
			graph_pairs.append((cid, 1.0))

		# RRF (Reciprocal Rank Fusion) with configurable weights
		# RRF score = w1/(k1 + rank1) + w2/(k2 + rank2) + ...
		# where k1, k2 are rank constants (typically 60), w1, w2 are weights
		k_constant = 60.0  # Standard RRF constant
		rrf_scores: Dict[str, float] = {}

		# Diagnostics: keep top ids before fusion
		_before_vec = [rid for rid, _ in vec_pairs[:max(1, top_k)]]
		_before_graph = [rid for rid, _ in graph_pairs[:max(1, top_k)]]
		
		# Vector ranking contribution
		for rank, (_id, _) in enumerate(vec_pairs):
			rrf_scores[_id] = rrf_scores.get(_id, 0.0) + w_vec / (k_constant + rank + 1)
		
		# Graph ranking contribution
		for rank, (_id, _) in enumerate(graph_pairs):
			rrf_scores[_id] = rrf_scores.get(_id, 0.0) + w_g / (k_constant + rank + 1)

		# Rank by RRF score and cut
		ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
		ranked_ids = [rid for rid, _ in ranked_ids[:max(1, top_k)]]

		# Emit diagnostics via std logging (lightweight)
		try:
			from datainsight_agent.common.logging import get_logger
			_logger = get_logger("retrieval")
			_logger.info("rrf_fusion", before_vec=_before_vec, before_graph=_before_graph, after_ranked=ranked_ids,
				w_vec=w_vec, w_graph=w_g, k_constant=k_constant, top_k=top_k)
		except Exception as e:
			# 避免编码问题
			try:
				print(f"[DEBUG] RRF fusion logging failed: {str(e)}")
			except UnicodeError:
				print(f"[DEBUG] RRF fusion logging failed: encoding error")
			pass

		# Materialize KBEntity via graph if available; else fallback by id mapping in index meta path
		entities: List[KBEntity] = []
		if self.local_graph and ranked_ids:
			try:
				rows = self.local_graph.get_by_ids(ranked_ids, limit=top_k)
				for row in rows:
					try:
						entities.append(KBEntity(**row))
					except Exception:
						continue
			except Exception as e:
				try:
					print(f"[DEBUG] Graph get_by_ids failed: {str(e)}")
				except UnicodeError:
					print(f"[DEBUG] Graph get_by_ids failed: encoding error")
		# Fallback: if graph is not present, attempt name/alias match again to map id strings
		if not entities and self.local_graph:
			try:
				rows = self.local_graph.find_by_concepts(concepts, limit=top_k)
				for row in rows:
					try:
						entities.append(KBEntity(**row))
					except Exception:
						continue
			except Exception as e:
				try:
					print(f"[DEBUG] Graph find_by_concepts failed: {str(e)}")
				except UnicodeError:
					print(f"[DEBUG] Graph find_by_concepts failed: encoding error")

		# Deduplicate by id while preserving order
		seen = set()
		uniq: List[KBEntity] = []
		for e in entities:
			if e.id in seen:
				continue
			seen.add(e.id)
			uniq.append(e)
		return uniq
