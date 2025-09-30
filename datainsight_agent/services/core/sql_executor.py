"""
LEGACY: Original SQL executor used by the pipeline.

Bridged by the component `components.sql_generator.SQLExecutorComponent`.
Prefer using the component interface in new code.
"""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from datainsight_agent.config.settings import Settings


class SQLExecutor:
	"""Simple read-only SQL executor.

	- Enforces SELECT-only
	- Optional row limit
	"""

	def __init__(self, settings: Settings) -> None:
		if not settings.database_url:
			raise RuntimeError("DATABASE_URL not configured")
		self.engine: Engine = create_engine(settings.database_url)

	def execute(self, sql: str, limit: Optional[int] = 100) -> List[dict[str, Any]]:
		clean = sql.strip().rstrip(";")
		if not clean.lower().startswith("select"):
			raise ValueError("Only SELECT queries are allowed for execution")
		if limit is not None and " limit " not in clean.lower():
			clean = f"{clean} LIMIT {int(limit)}"
		with self.engine.connect() as conn:
			result = conn.execute(text(clean))
			rows = result.mappings().all()
			return [dict(r) for r in rows]
