from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def main() -> None:
	db_path_str = os.getenv("DB_PATH", "datainsight.db")
	db_path = Path(db_path_str)
	if not db_path.exists():
		print(json.dumps({"exists": False, "error": "db_not_found", "db": str(db_path)}))
		return
	conn = sqlite3.connect(str(db_path))
	try:
		cur = conn.cursor()
		from datainsight_agent.config.settings import load_settings
		s = load_settings()
		tbl = s.dw_table
		tcol = s.dw_time_column
		cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'")
		row = cur.fetchone()
		if row is None:
			print(json.dumps({"exists": False, "table": tbl}, ensure_ascii=False))
			return
		months = [r[0] for r in cur.execute(f"SELECT DISTINCT {tcol} FROM {tbl} ORDER BY {tcol}").fetchall()]
		min_month, max_month = cur.execute(f"SELECT MIN({tcol}), MAX({tcol}) FROM {tbl}").fetchone()
		print(json.dumps({
			"exists": True,
			"table": tbl,
			"months": months,
			"min": min_month,
			"max": max_month,
		}, ensure_ascii=False))
	finally:
		conn.close()


if __name__ == "__main__":
	main()


