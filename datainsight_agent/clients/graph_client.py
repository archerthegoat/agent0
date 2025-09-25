from __future__ import annotations

from typing import Any, Dict, List
import json
import sqlite3
from pathlib import Path


class LocalGraphClient:
	"""SQLite-based minimal graph-like store for KB entities."""

	def __init__(self, db_path: str) -> None:
		self.path = Path(db_path)
		self.conn = sqlite3.connect(str(self.path))
		# performance pragmas for read-mostly workload
		try:
			self.conn.execute("PRAGMA journal_mode=WAL;")
			self.conn.execute("PRAGMA synchronous=NORMAL;")
			self.conn.execute("PRAGMA temp_store=MEMORY;")
			self.conn.execute("PRAGMA mmap_size=268435456;")  # 256MB
		except Exception:
			pass
		self.conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS entities (
				id TEXT PRIMARY KEY,
				data TEXT NOT NULL
			);
			"""
		)
		self.conn.commit()

	def close(self) -> None:
		self.conn.close()

	def upsert_entity(self, entity: Dict[str, Any]) -> None:
		self.conn.execute(
			"INSERT OR REPLACE INTO entities (id, data) VALUES (?, ?)",
			(entity["id"], json.dumps(entity, ensure_ascii=False)),
		)
		self.conn.commit()

	def find_by_concepts(self, concepts: List[str], limit: int = 5) -> List[Dict[str, Any]]:
		if not concepts:
			return []
		rows = self.conn.execute("SELECT data FROM entities").fetchall()
		out: List[Dict[str, Any]] = []
		for (data_str,) in rows:
			try:
				obj = json.loads(data_str)
				name = str(obj.get("canonical_name", ""))
				aliases = obj.get("aliases", []) or []
				text = " ".join([name] + aliases).lower()
				if any(c.lower() in text for c in concepts):
					out.append(obj)
			except Exception:
				continue
		# preserve order and limit
		return out[:limit]

	def get_by_ids(self, ids: List[str], limit: int | None = None) -> List[Dict[str, Any]]:
		"""Fetch entities by exact ids using the SQLite store."""
		if not ids:
			return []
		# Deduplicate and cap placeholders to reasonable size
		uniq = list(dict.fromkeys([str(i) for i in ids]))
		placeholders = ",".join(["?"] * len(uniq))
		query = f"SELECT data FROM entities WHERE id IN ({placeholders})"
		rows = self.conn.execute(query, tuple(uniq)).fetchall()
		out: List[Dict[str, Any]] = []
		for (data_str,) in rows:
			try:
				out.append(json.loads(data_str))
			except Exception:
				continue
		return out[:limit] if (limit is not None) else out


