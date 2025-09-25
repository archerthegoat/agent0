from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from datainsight_agent.cli import db_init_dw_lite, db_seed_synthetic


def check_months(db_path: Path) -> dict:
	conn = sqlite3.connect(str(db_path))
	try:
		cur = conn.cursor()
		cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dws_user_activity_monthly'")
		if cur.fetchone() is None:
			return {"exists": False}
		months = [r[0] for r in cur.execute("SELECT DISTINCT month FROM dws_user_activity_monthly ORDER BY month").fetchall()]
		min_month, max_month = cur.execute("SELECT MIN(month), MAX(month) FROM dws_user_activity_monthly").fetchone()
		return {"exists": True, "months": months, "min": min_month, "max": max_month}
	finally:
		conn.close()


def main() -> None:
	# Recreate and seed
	db_path = os.getenv("DB_PATH", "datainsight.db")
	db = Path(db_path)
	db_init_dw_lite(db_path=db)
	db_seed_synthetic(rows=20000, months=6, start_month="2025-09", chunk_size=1000, yes=True, output=Path(""), use_llm=True)

	# Check months
	res = check_months(db)
	print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
	main()


