from __future__ import annotations

import json
from pathlib import Path
from typing import List
from subprocess import run, PIPE


def run_one(query: str) -> dict:
	proc = run([
		"python", "-m", "_tools.rewrite_preview", query
	], stdout=PIPE, stderr=PIPE, text=True)
	return {
		"query": query,
		"stdout": proc.stdout,
		"stderr": proc.stderr,
		"returncode": proc.returncode,
	}


def main() -> None:
	queries: List[str] = [
		"不同区域的大区月活分布?",              # region 近义：区域/地域/大区
		"流量来源/渠道的最近一个月活跃如何?",    # channel 近义：渠道/来源/流量来源
		"会员等级/用户层级的MAU概况",            # user_level 近义：等级/层级/会员等级
		"客户端版本/版本号的月活分布",            # app_version 近义：版本/版本号/客户端版本
		"营销活动/投放活动对活跃的影响?",         # campaign 近义：活动/投放/营销活动
	]
	report_path = Path("batch_rewrite_report.jsonl")
	with report_path.open("w", encoding="utf-8") as f:
		for q in queries:
			res = run_one(q)
			f.write(json.dumps(res, ensure_ascii=False) + "\n")
	print(f"Wrote report: {report_path.resolve()}")


if __name__ == "__main__":
	main()
