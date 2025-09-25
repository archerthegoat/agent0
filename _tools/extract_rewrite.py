from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def parse_one(stdout: str) -> Dict:
	# Find the last JSON block between ```json and ``` or a loose JSON object
	start = stdout.rfind("```json")
	if start >= 0:
		end = stdout.find("```", start + 6)
		blob = stdout[start + 6:end] if end > start else stdout[start + 6:]
		try:
			return json.loads(blob)
		except Exception:
			pass
	# fallback: find first { ... }
	l = stdout.find("{")
	r = stdout.rfind("}")
	if l >= 0 and r > l:
		try:
			return json.loads(stdout[l : r + 1])
		except Exception:
			return {}
	return {}


def main() -> None:
	inp = Path("batch_rewrite_report.jsonl")
	outp = Path("batch_rewrite_extracted.jsonl")
	with inp.open("r", encoding="utf-8") as fin, outp.open("w", encoding="utf-8") as fout:
		for line in fin:
			obj = json.loads(line)
			rw = parse_one(obj.get("stdout", ""))
			row = {
				"query": obj.get("query"),
				"rewritten_question": rw.get("rewritten_question"),
				"metric": rw.get("metric"),
				"group_by": rw.get("group_by"),
				"time_filter": rw.get("time_filter"),
			}
			fout.write(json.dumps(row, ensure_ascii=False) + "\n")
	print(f"Wrote: {outp.resolve()}")


if __name__ == "__main__":
	main()
