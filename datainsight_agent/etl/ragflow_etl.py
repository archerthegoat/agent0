from __future__ import annotations

import json
from pathlib import Path
from typing import List

from datainsight_agent.common.logging import get_logger
from datainsight_agent.models.kb import KBEntity
from datainsight_agent.config.settings import load_settings
from datainsight_agent.clients.graph_client import LocalGraphClient
from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel

logger = get_logger(__name__)


def _load_kb_entities(source: Path) -> List[KBEntity]:
	entities: List[KBEntity] = []
	for p in sorted(source.glob("*.json")):
		try:
			data = json.loads(p.read_text(encoding="utf-8"))
			if isinstance(data, list):
				for item in data:
					entities.append(KBEntity(**item))
			else:
				entities.append(KBEntity(**data))
		except Exception as exc:
			logger.info("metadata_parse_failed", file=str(p), error=str(exc))
	return entities


def _upsert_local_graph(client: LocalGraphClient, entities: List[KBEntity], dry_run: bool) -> None:
	for e in entities:
		obj = {
			"id": e.id,
			"canonical_name": e.canonical_name,
			"aliases": e.aliases,
			"type": e.type,
			"what": e.what.model_dump() if e.what else None,
			"why": e.why.model_dump() if e.why else None,
			"how": e.how.model_dump() if e.how else None,
			"who": e.who.model_dump() if e.who else None,
			"when": e.when.model_dump() if e.when else None,
			"where": e.where.model_dump() if e.where else None,
		}
		if dry_run:
			logger.info("local_graph_upsert_dry_run", id=e.id, name=e.canonical_name)
			continue
		client.upsert_entity(obj)


def _entity_text(e: KBEntity) -> str:
	parts: List[str] = [e.canonical_name] + e.aliases
	if e.what and e.what.description:
		parts.append(e.what.description)
	if e.how and e.how.formula_human:
		parts.append(e.how.formula_human)
	if e.how and e.how.data_source:
		ds = e.how.data_source
		parts.append(f"{ds.layer}:{ds.table}.{ds.column or ''}")
	return "\n".join([p for p in parts if p])


def _upsert_milvus_vectors(entities: List[KBEntity], s) -> None:
	"""Upsert entities to Milvus vector store."""
	from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel
	
	embedder = EmbeddingModel()
	ids = []
	texts = []
	metas = []
	for e in entities:
		ids.append(e.id)
		texts.append(f"{e.canonical_name} {' '.join(e.aliases)}")
		metas.append({
			"id": e.id,
			"canonical_name": e.canonical_name,
			"aliases": e.aliases,
			"type": e.type,
		})
	vectors = embedder.embed(texts)
	actual_dim = len(vectors[0]) if vectors and len(vectors[0]) > 0 else int(s.vector_dim)
	store = MilvusVectorStore(dim=actual_dim, space=str(s.vector_space))
	store.add(ids=ids, vectors=vectors, metadatas=metas)
	logger.info("milvus_upsert_done", count=len(ids), dim=actual_dim)


def _build_hnsw_index(entities: List[KBEntity], dry_run: bool) -> None:
	"""Build/update local HNSW vector index from KB entities."""
	s = load_settings()
	if dry_run:
		logger.info("hnsw_upsert_dry_run", count=len(entities), index_dir=s.vector_index_dir)
		return
	embedder = EmbeddingModel()
	texts = [_entity_text(e) for e in entities]
	ids = [e.id for e in entities]
	metas = []
	for e in entities:
		metas.append({
			"id": e.id,
			"canonical_name": e.canonical_name,
			"aliases": e.aliases,
			"type": e.type,
		})
	vectors = embedder.embed(texts)
	actual_dim = len(vectors[0]) if vectors and len(vectors[0]) > 0 else int(s.vector_dim)
	store = MilvusVectorStore(dim=actual_dim, space=str(s.vector_space))
	store.add(ids=ids, vectors=vectors, metadatas=metas)
	logger.info("milvus_upsert_done", count=len(ids), dim=actual_dim)


def run_ragflow_etl(source: Path, yes: bool = False, dry_run: bool = True) -> None:
	"""Run ETL pipeline using RAGFlow outputs as input.

	- Parse JSON under `source` into KB entities
	- Upsert entities into local graph backend (SQLite)
	- Build/update local HNSW vector index for semantic retrieval
	- Dry-run logs actions unless `yes=True`
	"""
	if not source.exists() or not source.is_dir():
		raise FileNotFoundError(f"ETL source not found: {source}")

	s = load_settings()
	logger.info("etl_start", source=str(source), dry_run=dry_run, confirmed=yes)
	entities = _load_kb_entities(source)
	logger.info("metadata_loaded", count=len(entities))

	# Local graph backend
	try:
		lg = LocalGraphClient(s.local_graph_path)
		try:
			_upsert_local_graph(lg, entities, dry_run=(dry_run or not yes))
			logger.info("local_graph_done", wrote=not (dry_run or not yes), path=s.local_graph_path)
		finally:
			lg.close()
	except Exception as exc:
		logger.info("graph_write_skip", error=str(exc))

	# Local HNSW vector index (always available locally)
	try:
		_build_hnsw_index(entities, dry_run=(dry_run or not yes))
	except Exception as exc:
		logger.info("hnsw_skip", error=str(exc))

	# Milvus vector store upsert
	if getattr(s, "milvus_enabled", False):
		if not dry_run:
			_upsert_milvus_vectors(entities, s)
		else:
			logger.info("milvus_upsert_dry_run", count=len(entities))
	
	# Placeholders for external stores: ES/Neo4j are disabled by default
	if getattr(s, "es_enabled", False):
		logger.info("es_write_skip", reason="Phase1 placeholder; disabled or not implemented")
	if getattr(s, "neo4j_enabled", False) and getattr(s, "graph_backend", "local") != "neo4j":
		logger.info("neo4j_write_skip", reason="Phase1 placeholder; using local graph backend")

	logger.info("etl_done", wrote=not (dry_run or not yes))
