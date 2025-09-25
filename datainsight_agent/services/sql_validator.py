from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel
import sqlglot
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class SQLValidationResult(BaseModel):
	valid: bool
	errors: List[str]
	warnings: List[str]
	explain: Optional[str] = None


class SQLValidator:
	"""Validate SQL for syntax and safety, with optional live EXPLAIN.

	- Syntax: parsed by sqlglot with inferred dialect
	- Safety: only SELECT, single statement, ban DDL/DML keywords
	- Live: run EXPLAIN if a database_url is provided
	"""

	_FORBIDDEN_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE"}

	def validate(self, sql: str, database_url: Optional[str] = None, do_explain: bool = False) -> SQLValidationResult:
		errors: List[str] = []
		warnings: List[str] = []

		# Basic sanitation
		if ";" in sql.strip().rstrip(";"):
			errors.append("Multiple statements are not allowed.")

		# Infer dialect
		dialect = self._infer_dialect(database_url)

		# Syntax check
		try:
			if dialect:
				parsed = sqlglot.parse_one(sql, read=dialect)
			else:
				parsed = sqlglot.parse_one(sql)
		except Exception as exc:
			errors.append(f"Syntax error: {exc}")
			return SQLValidationResult(valid=False, errors=errors, warnings=warnings)

		# Safety checks
		if parsed is None:
			errors.append("Empty SQL or parse failed.")
			return SQLValidationResult(valid=False, errors=errors, warnings=warnings)

		if parsed.key.upper() != "SELECT":
			errors.append("Only SELECT queries are allowed.")

		upper = sql.upper()
		forbidden_found = [kw for kw in self._FORBIDDEN_KEYWORDS if kw in upper]
		if forbidden_found:
			errors.append(f"Forbidden keywords present: {', '.join(sorted(forbidden_found))}")

		# Optional EXPLAIN
		explain_text: Optional[str] = None
		if not errors and do_explain and database_url:
			try:
				engine = create_engine(database_url)
				explain_text = self._run_explain(engine, sql)
			except Exception as exc:
				warnings.append(f"EXPLAIN failed: {exc}")

		return SQLValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings, explain=explain_text)

	def _infer_dialect(self, database_url: Optional[str]) -> Optional[str]:
		if not database_url:
			return None
		lower = database_url.lower()
		if lower.startswith("sqlite:"):
			return "sqlite"
		if lower.startswith("postgres"):
			return "postgres"
		if lower.startswith("mysql") or lower.startswith("mariadb"):
			return "mysql"
		return None

	def _run_explain(self, engine: Engine, sql: str) -> str:
		dialect = engine.dialect.name
		stmt = sql
		if dialect == "sqlite":
			stmt = f"EXPLAIN QUERY PLAN {sql}"
		elif dialect in {"postgresql", "postgres"}:
			stmt = f"EXPLAIN {sql}"
		elif dialect in {"mysql", "mariadb"}:
			stmt = f"EXPLAIN {sql}"
		else:
			stmt = f"EXPLAIN {sql}"
		with engine.connect() as conn:
			res = conn.execute(text(stmt))
			rows = res.fetchall()
			return "\n".join([" | ".join([str(col) for col in row]) for row in rows])
