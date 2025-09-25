from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path

import typer
from rich import print

from datainsight_agent.config.settings import load_settings


def ask_time() -> str:
	try:
		return typer.prompt("请填写时间范围(YYYY-MM,YYYY-MM，示例: 2024-05,2024-05)", default="").strip()
	except Exception:
		return ""


def ask_metric(default_val: str = "") -> str:
	try:
		val = (typer.prompt("请填写指标（例如：MAU/UV/PV），必填", default=default_val) or "").strip()
		return val.lower()
	except Exception:
		return ""


def compute_default_window(settings=None) -> str:
	from datetime import datetime as _dt
	from sqlalchemy import create_engine, text as _text
	s = settings or load_settings()
	win = int(getattr(s, "default_time_window_months", 12) or 12)
	time_col = getattr(s, "dw_time_column", "month") or "month"
	y, mm = None, None
	try:
		if s.database_url:
			engine = create_engine(s.database_url)
			with engine.connect() as conn:
				row = conn.execute(_text(f"SELECT MAX({time_col}) FROM {s.dw_table}")).fetchone()
				mx = row[0] if row else None
				if mx and isinstance(mx, str) and len(mx) >= 7 and mx[:4].isdigit():
					y, mm = int(mx[:4]), int(mx[5:7])
	except Exception:
		pass
	if y is None or mm is None:
		now = _dt.now(); y, mm = now.year, now.month
	end_total = y * 12 + (mm - 1)
	start_total = end_total - (win - 1)
	sy, sm = divmod(start_total, 12); ey, em = divmod(end_total, 12)
	return f"{sy:04d}-{sm+1:02d},{ey:04d}-{em+1:02d}"


def print_plan_ir_sql(final: Dict[str, Any], settings=None, validate: bool = False, live: bool = False, execute: bool = False) -> None:
	"""统一打印 Plan/IR/SQL，并可选做校验与执行。"""
	s = settings or load_settings()
	plan = final.get("plan"); sql = final.get("sql"); ir = final.get("ir")
	print(f"[blue]Plan:[/blue] {plan}")
	
	# 显示归因分析报告
	attribution_report = final.get("attribution_report")
	if attribution_report:
		print("\n[green]📊 归因分析报告[/green]")
		print(attribution_report)
		print("\n" + "="*50 + "\n")
	# else:
		# print(f"[DEBUG] 没有找到归因分析报告，final keys: {list(final.keys())}")
		# # 检查是否有归因分析配置
		# ir = final.get("ir", {})
		# attribution_analysis = ir.get("attribution_analysis")
		# if attribution_analysis:
		# 	print(f"[DEBUG] 发现归因分析配置: {attribution_analysis}")
		# else:
		# 	print("[DEBUG] 没有归因分析配置")
	
	# 显示IR验证结果
	ir_validation = final.get("ir_validation")
	if ir_validation:
		if ir_validation.get("warnings"):
			print("[yellow]IR Warnings:[/yellow]")
			for warning in ir_validation["warnings"]:
				print(f"  - {warning}")
		if ir_validation.get("suggestions"):
			print("[cyan]IR Suggestions:[/cyan]")
			for suggestion in ir_validation["suggestions"]:
				print(f"  - {suggestion}")
		if ir_validation.get("errors"):
			print("[red]IR Errors:[/red]")
			for error in ir_validation["errors"]:
				print(f"  - {error}")
	
	# 显示全局警告和建议
	if final.get("warnings"):
		print("[yellow]Warnings:[/yellow]")
		for warning in final["warnings"]:
			print(f"  - {warning}")
	if final.get("suggestions"):
		print("[cyan]Suggestions:[/cyan]")
		for suggestion in final["suggestions"]:
			print(f"  - {suggestion}")
	
	if ir:
		print("[blue]IR:[/blue]", ir)
	if not sql:
		return
	print("[cyan]Generated SQL:[/cyan]")
	print(sql)
	if validate:
		from datainsight_agent.services.sql_validator import SQLValidator
		val = SQLValidator().validate(sql, database_url=s.database_url if live else None, do_explain=live)
		if val.errors:
			print("[red]SQL validation errors:[/red]")
			for e in val.errors:
				print(f"- {e}")
		if val.warnings:
			print("[yellow]SQL validation warnings:[/yellow]")
			for w in val.warnings:
				print(f"- {w}")
		if val.explain:
			print("[magenta]EXPLAIN:[/magenta]")
			print(val.explain)
	rows_count = None
	if execute and s.database_url and sql:
		from datainsight_agent.services.sql_executor import SQLExecutor
		rows = SQLExecutor(s).execute(sql, limit=10)
		print("[green]Rows (up to 10):[/green]")
		for r in rows:
			print(r)
		rows_count = len(rows)
	# 仅用于统一接口；日志写入由调用方处理
	return None


def print_timings(timings: list[dict]) -> None:
	"""统一打印 timings 表格（秒）。"""
	if not timings:
		print("[yellow][WARN] No timings captured.[/yellow]")
		return
	base = min([t.get('start_ts_ms', 0) for t in timings]) if timings else 0
	print("\n[white]Timing (s):[/white]")
	print("node\tstart_s\tend_s\tduration_s")
	for t in timings:
		start_s = (t.get('start_ts_ms', base) - base) / 1000.0
		end_s = (t.get('end_ts_ms', base) - base) / 1000.0
		dur_s = (t.get('duration_ms', 0) / 1000.0)
		node_name = t.get('node')
		
		# 显示跳过原因
		skip_info = ""
		if t.get('skipped_llm'):
			skip_info = " [SKIPPED_LLM]"
		elif t.get('skipped_reason'):
			reason = t.get('skipped_reason')
			if reason == "no_time_filter":
				skip_info = " [SKIPPED:no_time_filter]"
			elif reason == "no_time_filter_and_no_kb_needed":
				skip_info = " [SKIPPED:no_time_filter_and_no_kb_needed]"
			else:
				skip_info = f" [SKIPPED:{reason}]"
		
		print(f"{node_name}{skip_info}\t{start_s:.3f}\t{end_s:.3f}\t{dur_s:.3f}")


def append_log_line(event: str, **fields) -> None:
	"""轻量日志落盘，写入 logs/agent_calls.log。"""
	try:
		from pathlib import Path as _P
		from datetime import datetime as _dt, timezone as _tz
		import os as _os
		# 使用配置化的日志文件名
		from datainsight_agent.config.settings import load_settings
		s = load_settings()
		log_path = _P("logs") / s.log_files.get("calls", "agent_calls.log")
		log_path.parent.mkdir(parents=True, exist_ok=True)
		trace_id = fields.get("trace_id") or _os.getenv("TRACE_ID") or ""
		line = {"event": event, "timestamp": _dt.now(_tz.utc).isoformat(), "trace_id": trace_id, **fields}
		with log_path.open("a", encoding="utf-8") as f:
			f.write(__import__("json").dumps(line, ensure_ascii=False) + "\n")
	except Exception:
		pass


def validate_and_maybe_execute_inplace(final: Dict[str, Any], settings=None, validate: bool = False, live: bool = False, execute: bool = False) -> Dict[str, Any]:
	"""对 final 中的 sql 执行校验/可选执行，结果写回 final 并返回。同 print_plan_ir_sql 的校验/执行路径。"""
	s = settings or load_settings()
	if final.get("sql") and validate:
		from datainsight_agent.services.sql_validator import SQLValidator
		val = SQLValidator().validate(final["sql"], database_url=s.database_url if live else None, do_explain=live)
		final["validation"] = val.model_dump()
		if execute and s.database_url:
			try:
				from datainsight_agent.services.sql_executor import SQLExecutor
				rows = SQLExecutor(s).execute(final["sql"], limit=10)
				final["rows"] = rows
			except Exception as exc:
				final["exec_error"] = str(exc)
	return final


class env_temporary:  # simple context manager for env vars
	def __init__(self, vars_map: Dict[str, str | None]):
		self.vars_map = vars_map
		self._prev: Dict[str, str | None] = {}

	def __enter__(self):
		import os as _os
		for k, v in (self.vars_map or {}).items():
			self._prev[k] = _os.getenv(k)
			if v is None:
				try:
					del _os.environ[k]
				except Exception:
					pass
			else:
				_os.environ[k] = str(v)
		return self

	def __exit__(self, exc_type, exc, tb):
		import os as _os
		for k, v in self._prev.items():
			if v is None:
				try:
					del _os.environ[k]
				except Exception:
					pass
			else:
				_os.environ[k] = v
		return False


def get_agent_or_exit() -> Any:
	"""Return LlamaIndex pipeline agent or exit with error message."""
	try:
		from datainsight_agent.orchestrator.li import build_pipeline as _build_li
		return _build_li()
	except Exception as _e:  # pragma: no cover
		print(f"[red][ERROR] LlamaIndex engine unavailable: {_e}")
		import typer as _typer
		raise _typer.Exit(code=1)


def setup_cli_command() -> Any:
	"""Common setup for CLI commands: load settings and configure logging."""
	from datainsight_agent.common.logging import configure_logging
	s = load_settings()
	configure_logging(s)
	return s


def stream_collect(agent: Any, state: Dict[str, Any]) -> Dict[str, Any]:
	final: Dict[str, Any] = {}
	for values in agent.stream(state, stream_mode="values"):
		if isinstance(values, dict):
			final.update(values)
	return final


def test_logging(message: str, log_path: Path = None) -> None:
	"""Test logging functionality with multiple approaches."""
	from datainsight_agent.common.logging import get_logger
	from pathlib import Path as _P
	import logging as _logging
	
	logger = get_logger("log_test")
	logger.info("manual_test", message=message)
	
	# Also emit via stdlib root logger for verification
	_logging.getLogger().info("manual_test_stdlib", extra={"test_message": message})
	
	# Flush handlers explicitly
	for h in _logging.getLogger().handlers:
		try:
			h.flush()
		except Exception:
			pass
	
	# Direct append as a fallback to verify file path
	if log_path:
		try:
			log_path.parent.mkdir(parents=True, exist_ok=True)
			with log_path.open("a", encoding="utf-8") as f:
				f.write('{"logger":"log_test","event":"manual_test_fallback","message":"' + str(message) + '"}\n')
		except Exception:
			pass
		print("[green]Logged.[/green] path=", log_path)
	else:
		print("[green]Logged.[/green]")


def generate_synthetic_data(rows: int, months: int, start_month: str, chunk_size: int, use_llm: bool) -> List[dict]:
	"""Generate synthetic data rows using LLM or local fallback."""
	from datainsight_agent.services.synthetic_data import (
		month_list as synth_month_list,
		local_generate as synth_local_generate,
		llm_generate as synth_llm_generate,
	)
	
	month_values = synth_month_list(start_month, months)
	all_rows: List[dict] = []
	remaining = rows
	while remaining > 0:
		batch = min(chunk_size, remaining)
		part = synth_llm_generate(batch, month_values) if use_llm else synth_local_generate(batch, month_values)
		all_rows.extend(part)
		remaining -= batch
	return all_rows


def write_ndjson_output(all_rows: List[dict], output: Path) -> bool:
	"""Write synthetic data to NDJSON file if output path is valid."""
	if output and str(output).strip() and str(output).strip() not in {".", "./", ".\\"} and not output.is_dir():
		output.parent.mkdir(parents=True, exist_ok=True)
		with output.open("w", encoding="utf-8") as f:
			for r in all_rows:
				f.write(__import__("json").dumps(r, ensure_ascii=False) + "\n")
		print(f"[green]Wrote NDJSON:[/green] {output}")
		return True
	return False


def load_kb_entities(metadata_dir: Path = None) -> List[Any]:
	"""Load KB entities from metadata directory."""
	from datainsight_agent.models.kb import KBEntity
	import json as _json
	
	if metadata_dir is None:
		metadata_dir = Path("metadata")
	
	entities: List[KBEntity] = []
	if metadata_dir.exists():
		try:
			data = []
			for p in sorted(metadata_dir.glob("*.json")):
				obj = _json.loads(p.read_text(encoding="utf-8"))
				if isinstance(obj, list):
					data.extend(obj)
				else:
					data.append(obj)
			for item in data:
				try:
					entities.append(KBEntity(**item))
				except Exception:
					continue
		except Exception:
			entities = []
	return entities


def entity_to_text(e: Any) -> str:
	"""Convert KB entity to text representation."""
	parts: List[str] = [e.canonical_name] + e.aliases
	if e.what and e.what.description:
		parts.append(e.what.description)
	if e.how and e.how.formula_human:
		parts.append(e.how.formula_human)
	if e.how and e.how.data_source:
		ds = e.how.data_source
		parts.append(f"{ds.layer}:{ds.table}.{ds.column or ''}")
	return "\n".join([p for p in parts if p])


def build_ir_from_metric(metric: str, group_by: str = "", month: str = "", settings: Any = None) -> Any:
	"""Build SemanticQueryIR from metric, group_by, and optional month filter."""
	from datainsight_agent.models.ir import SemanticQueryIR, SemanticAggregation, SemanticFilter
	from datainsight_agent.services.metric_registry import MetricRegistry
	
	ir = SemanticQueryIR()
	
	# group-by columns as provided
	gb_cols = [c.strip() for c in group_by.split(",") if c.strip()]
	for c in gb_cols:
		ir.group_by.append(c)

	# Resolve metric via MetricRegistry (no hardcoding)
	reg = MetricRegistry()
	mdef = reg.resolve_from_signals([metric])
	if not mdef:
		raise ValueError("Metric not found in registry. Please add to metadata/metrics.json.")
	
	ag = mdef.aggregation or {}
	func = str(ag.get("function") or "").upper() or "COUNT"
	field = str(ag.get("field") or "").strip() or None
	alias = str(ag.get("alias") or "").strip() or None
	ir.aggregations.append(SemanticAggregation(function=func, field=field, alias=alias))
	
	for f in (mdef.filters or []):
		fld = str(f.get("field") or "").strip()
		op = str(f.get("operator") or "=").strip()
		val = str(f.get("value") or "").strip()
		if fld:
			ir.filters.append(SemanticFilter(field=fld, operator=op, value=val))

	# Optional month
	if month:
		time_col = settings.dw_time_column or "month" if settings else "month"
		ir.filters.append(SemanticFilter(field=time_col, operator="=", value=month))
	
	return ir


def get_kb_context_for_sql_preview(question: str, top_k: int = 6) -> str:
	"""Get KB context for SQL preview command."""
	from datainsight_agent.models.kb import KBEntity
	import json as _j
	
	lines: List[str] = []
	try:
		from pathlib import Path as _P
		md = _P("metadata")
		if md.exists():
			ents: List[KBEntity] = []
			for p in sorted(md.glob("*.json")):
				obj = _j.loads(p.read_text(encoding="utf-8"))
				arr = obj if isinstance(obj, list) else [obj]
				for it in arr:
					try:
						ents.append(KBEntity(**it))
					except Exception:
						continue
			for e in ents[:top_k]:
				ds = e.how.data_source if (e.how and e.how.data_source) else None
				src = f" table={ds.table}, column={ds.column}" if ds else ""
				aliases = "|".join(e.aliases)
				lines.append(f"id={e.id}, name={e.canonical_name}, aliases={aliases}, type={e.type}{src}")
	except Exception:
		pass
	return "\n".join(lines)


def get_latest_year_range(db_path: str) -> tuple[str, str]:
	"""Get latest year range from database."""
	import sqlite3 as _sqlite3
	conn = _sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		# 使用配置化的表名
		from datainsight_agent.config.settings import load_settings
		s = load_settings()
		table_name = s.dw_table or "dws_user_activity_monthly"
		mx = cur.execute(f"SELECT MAX(month) FROM {table_name}").fetchone()[0]
		if not mx:
			# 使用当前年份作为默认值
			from datetime import datetime
			current_year = datetime.now().year
			return (f"{current_year}-01", f"{current_year}-12")
		year, mon = map(int, mx.split("-"))
		end_total = year * 12 + (mon - 1)
		start_total = end_total - 11
		sy, sm = divmod(start_total, 12)
		ey, em = divmod(end_total, 12)
		return (f"{sy:04d}-{sm+1:02d}", f"{ey:04d}-{em+1:02d}")
	finally:
		conn.close()


def probe_columns(db_path: str) -> List[str]:
	"""Probe database columns."""
	import sqlite3 as _sqlite3
	conn = _sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		# 使用配置化的表名
		from datainsight_agent.config.settings import load_settings
		s = load_settings()
		table_name = s.dw_table or "dws_user_activity_monthly"
		rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
		return [r[1] for r in rows]
	finally:
		conn.close()


def execute_sqlite_preview(sql: str, db_path: str) -> None:
	"""Execute SQL preview against local SQLite database."""
	import sqlite3 as _sqlite3
	
	conn = _sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		print("ROWS (first 20):")
		rows = cur.execute(sql).fetchmany(20)
		for r in rows:
			print(r)
	except Exception as exc:
		print(f"[red][ERROR] Execution failed:[/red] {exc}")
	finally:
		conn.close()


def run_parallel_tasks(jobs: List[tuple], pipeline_func, **kwargs) -> Dict[str, Dict[str, Any]]:
	"""Run parallel tasks using ThreadPoolExecutor."""
	from concurrent.futures import ThreadPoolExecutor, as_completed
	
	print(f"[blue]Parallel sub-tasks:[/blue] {len(jobs)} workers={max(1, kwargs.get('workers', 2))}")
	res_map: Dict[str, Dict[str, Any]] = {}
	
	with ThreadPoolExecutor(max_workers=max(1, kwargs.get('workers', 2))) as ex:
		futs = {}
		for tag, ov in jobs:
			futs[ex.submit(
				pipeline_func,
				kwargs.get('question', ''),
				metric_override=ov.get("metric", ""),
				time_filter_override=ov.get("time", ""),
				validate=kwargs.get('validate', False),
				live=kwargs.get('live', False),
				execute=kwargs.get('execute', False),
			)] = tag
		for fut in as_completed(futs):
			tag = futs[fut]
			try:
				res_map[tag] = fut.result()
			except Exception as exc:
				res_map[tag] = {"error": str(exc)}
	return res_map


def print_task_results(res_map: Dict[str, Dict[str, Any]], metric_a: str, metric_b: str, time_a: str, time_b: str) -> None:
	"""Print results for parallel tasks."""
	for tag in ["A", "B"]:
		res = res_map.get(tag) or {}
		print(f"\n[magenta]==== Task {tag} ====[/magenta]")
		if metric_a or metric_b or time_a or time_b:
			ovm = metric_a if tag == "A" else metric_b
			ovt = time_a if tag == "A" else time_b
			if ovm:
				print(f"[white]Override metric:[/white] {ovm}")
			if ovt:
				print(f"[white]Override time:[/white] {ovt}")
		# Unified printing
		from datainsight_agent.cli_helpers import print_plan_ir_sql as _print_plan_ir_sql
		_print_plan_ir_sql(res, validate=False, live=False, execute=False)


def perform_q2q_rewrite(question: str, top_k: int, settings: Any, show_prompt: bool = True) -> tuple[dict | None, str | None]:
	"""Perform Q2Q rewrite using RAG context."""
	from datainsight_agent.services.q2q import Q2QRewriter
	from datainsight_agent.services.llm import QwenClient
	from datainsight_agent.services.prompts import q2q_prompt
	import json as _json
	
	q2q_rewriter = Q2QRewriter()
	kb_context = q2q_rewriter._kb_context(question, top_k)
	print(f"[cyan]RAG - dynamic KB context:[/cyan]")
	print(kb_context)

	rewrite_prompt = q2q_prompt(kb_context, question)
	rewrite_json: dict | None = None
	resp: str | None = None
	
	try:
		client = QwenClient(settings)
		resp = client.generate_sql(rewrite_prompt)
		try:
			rewrite_json = _json.loads(resp)
		except Exception:
			rewrite_json = None
	except Exception as exc:
		resp = f"LLM error: {exc}"

	if show_prompt:
		print("[magenta]KB Context:[/magenta]")
		print(kb_context)
		print("[magenta]Prompt:[/magenta]")
		print(rewrite_prompt)
	print("[green]Rewrite result (raw):[/green]")
	print(resp if rewrite_json is None else _json.dumps(rewrite_json, ensure_ascii=False))
	
	return rewrite_json, resp


def normalize_time_filter(tf: str, q: str) -> str:
	"""Normalize time_filter from Q2Q/question to standard YYYY-MM,YYYY-MM format."""
	import re as _re
	tf = (tf or "").strip()
	# Already in canonical form
	if _re.match(r"\d{4}-\d{2},\d{4}-\d{2}", tf):
		return tf
	# Try to extract from question
	months = _re.findall(r"\d{4}-\d{2}", q)
	if len(months) >= 2:
		return f"{months[0]},{months[1]}"
	elif len(months) == 1:
		return f"{months[0]},{months[0]}"
	# Fallback to empty
	return ""



def handle_clarify_plan(final: dict, question: str, settings: Any, validate: bool, live: bool, execute: bool) -> bool:
    """Handle clarify plan by auto-filling missing info (no interactive prompts)."""
    error_response = final.get("response", "")

    # 当前状态中的信息
    q2q = final.get("q2q", {})
    current_metrics = [str(m) for m in (q2q.get("metric") or [])]
    current_time = str(q2q.get("time_filter") or "").strip()

    # 推断缺失信息（既依赖提示语，也基于状态与配置）
    needs_time = ("时间范围" in error_response) or ("时间" in error_response)
    time_required = bool(getattr(settings, "time_require_explicit", False))
    if not needs_time:
        needs_time = time_required and (current_time == "")

    needs_metric = ("度量" in error_response) or ("指标" in error_response) or ("MAU" in error_response)
    if not needs_metric:
        needs_metric = len(current_metrics) == 0

    # 目标输入（自动填充优先，完全无交互）
    t_in = current_time if current_time else ""
    m_in = current_metrics[0] if current_metrics else ""

    # 自动时间：从问题中规范化提取 YYYY-MM,YYYY-MM 或单月
    if needs_time and not t_in:
        try:
            t_in = normalize_time_filter("", question) or ""
        except Exception:
            t_in = ""

	# 自动指标：用注册表建议，选首个 metric_*（使用可解析的 canonical_name 而非 aggregation.alias）
    if needs_metric and not m_in:
        try:
            from datainsight_agent.services.metric_registry import MetricRegistry
            reg = MetricRegistry()
            cands = reg.suggest_from_text(question, top_k=5)
            def _is_metric(defn) -> bool:
                return str(getattr(defn, "metric_id", "")).startswith("metric_")
            mcands = [c for c in cands if _is_metric(c)]
            if mcands:
                m_in = str(mcands[0].canonical_name)
        except Exception:
            m_in = m_in or ""

    # 自动仍失败则直接退出（不进入交互）
    missing = []
    if needs_metric and not m_in:
        missing.append("度量")
    if needs_time and not t_in:
        missing.append("时间范围")
    if missing:
        print("[yellow]自动补全失败：缺少" + "/".join(missing) + "。[/yellow]")
        return False
	
    # 如果有任何输入，使用优化的重新运行方式
    if t_in or m_in:
        from datainsight_agent.orchestrator.li import build_pipeline as _build_li
        # 构造 state，带入覆盖，并要求 Q2Q 进行 enrich（不覆盖 metric/time）
        state = {
            "question": question,
            "q2q": {
                "metric": [m_in] if m_in else [],
                "time_filter": t_in or "",
            },
            "q2q_enrich_after_clarify": True,
            "clarified_inputs": {"metric": m_in or "", "time_filter": t_in or ""},
        }
        agent = _build_li()
        res: dict = {}
        for values in agent.stream(state, stream_mode="values"):
            if isinstance(values, dict):
                res.update(values)
        # 统一输出：仅通过 print_plan_ir_sql 打印，避免重复日志
        print_plan_ir_sql(res, settings=settings, validate=validate, live=live, execute=execute)
        final.pop("response", None)
        return True

    print("[red]No SQL produced by the graph (IR/KB). Please refine question or update KB.")
    return False


def handle_confirm_default_time_plan(final: dict, question: str, settings: Any, validate: bool, live: bool, execute: bool) -> bool:
	"""Handle confirm_default_time plan by asking user confirmation."""
	response = final.get("response", "未指定时间范围，将使用默认时间窗口。是否继续？")
	print(f"[yellow]{response}[/yellow]")
	
	try:
		confirm = typer.confirm("是否使用默认时间窗口继续？", default=True)
		if confirm:
			print("[yellow]已确认使用默认时间窗口，将重新执行查询。[/yellow]")
			win = compute_default_window(settings)
			m_in = ask_metric()
			if not m_in:
				print("[red]缺少指标，已取消本次执行。[/red]")
				return False
			# Re-run with overrides
			from datainsight_agent.cli import _run_pipeline_with_overrides
			res = _run_pipeline_with_overrides(
				question=question,
				metric_override=m_in,
				time_filter_override=win,
				validate=validate,
				live=live,
				execute=execute,
			)
			validate_and_maybe_execute_inplace(res, settings=settings, validate=validate, live=live, execute=execute)
			return True
		else:
			# 用户拒绝默认窗口，转入手动时间/指标
			t_in = ask_time()
			if t_in:
				m_in = ask_metric()
				from datainsight_agent.cli import _run_pipeline_with_overrides
				res = _run_pipeline_with_overrides(
					question=question,
					metric_override=m_in,
					time_filter_override=t_in,
					validate=validate,
					live=live,
					execute=execute,
				)
				validate_and_maybe_execute_inplace(res, settings=settings, validate=validate, live=live, execute=execute)
				return True
	except Exception as e:
		print(f"[red]确认处理失败: {e}[/red]")
		return False
	
	return False


def handle_sql_execution(sql: str, settings: Any, validate: bool, live: bool, execute: bool) -> int | None:
	"""Handle SQL validation and execution."""
	# SQL已经在print_plan_ir_sql中打印过了，这里不再重复打印
	
	# Use the unified validation and execution logic
	final = {"sql": sql}
	final = validate_and_maybe_execute_inplace(final, settings, validate, live, execute)
	
	# Print validation results
	if validate and final.get("validation"):
		val = final["validation"]
		if val.get("errors"):
			print("[red]SQL validation errors:[/red]")
			for e in val["errors"]:
				print(f"- {e}")
		if val.get("warnings"):
			print("[yellow]SQL validation warnings:[/yellow]")
			for w in val["warnings"]:
				print(f"- {w}")
		if val.get("explain"):
			print("[magenta]EXPLAIN:[/magenta]")
			print(val["explain"])
	
	# Print execution results
	if execute and final.get("rows") is not None:
		rows = final["rows"]
		print("[green]Rows (up to 10):[/green]")
		for r in rows:
			print(r)
		return len(rows)
	elif execute and final.get("exec_error"):
		print(f"[red]Execution error: {final['exec_error']}[/red]")
		return 0
	
	return None


def run_with_engine_override(engine: str, pipeline_func, *args, **kwargs):
	"""Run pipeline function with specific engine override."""
	import os as _os
	_prev_eng = _os.getenv("ORCHESTRATOR_ENGINE")
	try:
		_os.environ["ORCHESTRATOR_ENGINE"] = engine
		return pipeline_func(*args, **kwargs)
	finally:
		if _prev_eng is None:
			try:
				del _os.environ["ORCHESTRATOR_ENGINE"]
			except Exception:
				pass
		else:
			_os.environ["ORCHESTRATOR_ENGINE"] = _prev_eng


def validate_command_params(**params) -> None:
	"""Validate common command parameters and raise typer.Exit if invalid."""
	import typer
	
	# Check required database URL for certain operations
	if params.get("require_db") and not params.get("database_url"):
		print("[red]DATABASE_URL must be set in .env for this operation.[/red]")
		raise typer.Exit(code=1)
	
	# Check database type for specific operations
	if params.get("require_mysql") and params.get("database_url"):
		if not params["database_url"].lower().startswith("mysql"):
			print("[red]DATABASE_URL must be set to a MySQL URL in .env.[/red]")
			raise typer.Exit(code=1)
	
	if params.get("require_postgresql") and params.get("database_url"):
		if not (params["database_url"].lower().startswith("postgresql") or params["database_url"].lower().startswith("postgres")):
			print("[red]DATABASE_URL must be set to a PostgreSQL URL in .env.[/red]")
			raise typer.Exit(code=1)
	
	if params.get("require_clickhouse") and params.get("database_url"):
		if not params["database_url"].lower().startswith("clickhouse"):
			print("[red]DATABASE_URL must be set to a ClickHouse URL in .env.[/red]")
			raise typer.Exit(code=1)
	
	# Check confirmation for destructive operations
	if params.get("require_confirmation") and not params.get("yes"):
		print("[yellow]This operation may be destructive. Re-run with --yes to proceed.[/yellow]")
		raise typer.Exit(code=1)


def log_command_start(cmd: str, **fields) -> None:
	"""Log command start with common fields."""
	# Generate per-run trace id if not present and store to env for later logs
	import os as _os
	trace_id = fields.get("trace_id") or _os.getenv("TRACE_ID")
	if not trace_id:
		try:
			from uuid import uuid4 as _uuid4
			trace_id = _uuid4().hex
		except Exception:
			trace_id = ""
		_os.environ["TRACE_ID"] = trace_id
	append_log_line(f"{cmd}_start", cmd=cmd, trace_id=trace_id, **fields)


def log_command_end(cmd: str, success: bool = True, **fields) -> None:
	"""Log command end with common fields."""
	import os as _os
	trace_id = fields.get("trace_id") or _os.getenv("TRACE_ID") or ""
	append_log_line(f"{cmd}_end", cmd=cmd, ok=success, trace_id=trace_id, **fields)


def handle_command_error(cmd: str, error: Exception, **fields) -> None:
	"""Handle command error with consistent logging and user feedback."""
	import os as _os
	error_message = str(error)
	error_code = type(error).__name__
	try:
		error_detail = repr(error)
	except Exception:
		error_detail = error_message
	print(f"[red][ERROR] {error_message}[/red]")
	log_command_end(cmd, success=False, error_code=error_code, error_message=error_message, error_detail=error_detail, **fields)
	import typer
	raise typer.Exit(code=1)


