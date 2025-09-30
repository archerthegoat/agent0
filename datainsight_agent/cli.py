from __future__ import annotations
from pathlib import Path
from typing import List
import json as _json

import typer
from rich import print

from datainsight_agent.cli_helpers import (
	setup_cli_command, append_log_line, handle_command_error, log_command_start, log_command_end,
	generate_synthetic_data, write_ndjson_output, load_kb_entities, build_ir_from_metric,
	get_kb_context_for_sql_preview, get_latest_year_range, probe_columns, execute_sqlite_preview,
	run_parallel_tasks, print_task_results, perform_q2q_rewrite, normalize_time_filter,
	handle_clarify_plan, handle_confirm_default_time_plan, handle_sql_execution, run_with_engine_override,
	validate_command_params, print_timings, print_plan_ir_sql, validate_and_maybe_execute_inplace,
	ask_time, ask_metric, compute_default_window, test_logging, env_temporary
)
from datainsight_agent.common.logging import get_logger, configure_logging
from datainsight_agent.config.settings import load_settings
from datainsight_agent.etl.ragflow_etl import run_ragflow_etl
from datainsight_agent.models.kb import KBEntity
from datainsight_agent.services.db_bootstrap import init_sqlite_min, init_sqlite_dw_lite, init_mysql_min, init_postgresql_dw
from datainsight_agent.services.core.sql_generator import SQLGenerator
from datainsight_agent.services.sql_validator import SQLValidator
from datainsight_agent.services.llm import QwenClient
from datainsight_agent.services.prompts import sql_preview_system, sql_preview_prompt, q2q_prompt
from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel
from datainsight_agent.services.core.kb_vector_index import build_kb_vector_index
from datainsight_agent.services.registry.metric_retriever import build_metric_index


# 动态获取项目名称
def get_app_help() -> str:
	s = load_settings()
	return f"{s.project_info.get('name', 'DataInsight Agent')} CLI"

app = typer.Typer(help=get_app_help())

@app.command()
def check() -> None:
	"""Run basic environment checks."""
	s = setup_cli_command()
	logger = get_logger("check")
	logger.info("env_loaded", neo4j_uri=s.neo4j_uri, vector_index_dir=s.vector_index_dir)
	print("[green]Environment loaded successfully.[/green]")


@app.command(name="search-init")
def search_init() -> None:
	"""Initialize Elasticsearch index if ES is enabled; otherwise no-op."""
	s = setup_cli_command()
	if not getattr(s, "es_enabled", False):
		print("[yellow]ES_ENABLED is false. Skipping Elasticsearch initialization.[/yellow]")
		return
	print("[yellow]Elasticsearch init is not implemented in Phase 1. Skipping safely.[/yellow]")


@app.command(name="vector-init")
def vector_init() -> None:
	"""Initialize Milvus collection if Milvus is enabled; otherwise no-op."""
	s = setup_cli_command()
	if not getattr(s, "milvus_enabled", False):
		print("[yellow]MILVUS_ENABLED is false. Skipping Milvus initialization.[/yellow]")
		return
	print("[yellow]Milvus init is not implemented in Phase 1. Skipping safely.[/yellow]")


@app.command(name="graph-init")
def graph_init() -> None:
	"""Initialize Neo4j constraints if Neo4j is enabled; otherwise no-op (local graph used)."""
	s = setup_cli_command()
	if not getattr(s, "neo4j_enabled", False):
		print("[yellow]NEO4J_ENABLED is false. Skipping Neo4j initialization.[/yellow]")
		return
	print("[yellow]Neo4j init is not implemented in Phase 1. Using local graph backend.[/yellow]")


@app.command(name="db-create-indexes")
def db_create_indexes(
    table: str = typer.Option("", help="Target table name (default: DW_TABLE setting)"),
    dialect: str = typer.Option("", help="Force dialect sqlite/mysql/postgres/clickhouse (default: WAREHOUSE_DIALECT)"),
    skip_optional: bool = typer.Option(False, help="Skip optional indexes (like active column)"),
) -> None:
    """Create recommended indexes for analytics (safe, idempotent)."""
    s = setup_cli_command()
    logger = get_logger("db-create-indexes")
    if not s.database_url:
        print("[red]DATABASE_URL not configured.[/red]")
        raise typer.Exit(code=1)

    from sqlalchemy import create_engine, text
    engine = create_engine(s.database_url)
    tbl = (table or s.dw_table)
    d = (dialect or s.warehouse_dialect or "sqlite").lower()

    stmts = []
    if d in ("sqlite", "mysql", "postgres", "postgresql"):
        stmts = [
            f"CREATE INDEX IF NOT EXISTS idx_month ON {tbl}(month)",
            f"CREATE INDEX IF NOT EXISTS idx_month_channel ON {tbl}(month, channel_code)",
            f"CREATE INDEX IF NOT EXISTS idx_channel_user ON {tbl}(channel_code, user_id)",
        ]
        if not skip_optional:
            stmts.append(f"CREATE INDEX IF NOT EXISTS idx_active ON {tbl}(active)")
    elif d == "clickhouse":
        stmts = [
            f"ALTER TABLE {tbl} ADD INDEX IF NOT EXISTS idx_month month TYPE minmax GRANULARITY 1",
            f"ALTER TABLE {tbl} ADD INDEX IF NOT EXISTS idx_month_channel (month, channel_code) TYPE set(8192) GRANULARITY 1",
            f"ALTER TABLE {tbl} ADD INDEX IF NOT EXISTS idx_channel_user (channel_code, user_id) TYPE set(8192) GRANULARITY 1",
        ]
        if not skip_optional:
            pass
    else:
        print(f"[yellow]Unsupported dialect: {d}. Skipping.[/yellow]")
        return

    with engine.begin() as conn:
        for sql in stmts:
            try:
                conn.execute(text(sql))
                logger.info("index_created", sql=sql)
            except Exception as exc:
                logger.warning("index_creation_failed", sql=sql, error=str(exc))
                print(f"[yellow]Skip or failed: {sql} -> {exc}[/yellow]")

    print("[green]Indexes created/ensured.[/green]")


@app.command(name="db-show-indexes")
def db_show_indexes(
    table: str = typer.Option("", help="Target table name (default: DW_TABLE setting)"),
    dialect: str = typer.Option("", help="Force dialect sqlite/mysql/postgres/clickhouse (default: WAREHOUSE_DIALECT)"),
) -> None:
    """Show existing indexes for the target table (limited support per dialect)."""
    s = setup_cli_command()
    if not s.database_url:
        print("[red]DATABASE_URL not configured.[/red]")
        raise typer.Exit(code=1)
    from sqlalchemy import create_engine, text
    engine = create_engine(s.database_url)
    tbl = (table or s.dw_table)
    d = (dialect or s.warehouse_dialect or "sqlite").lower()

    rows = []
    with engine.connect() as conn:
        try:
            if d == "sqlite":
                res = conn.execute(text(f"PRAGMA index_list({tbl})"))
                rows = res.fetchall()
                for r in rows:
                    mp = getattr(r, "_mapping", None)
                    if mp is not None:
                        print(str(dict(mp)))
                    else:
                        try:
                            print(str(dict(r)))
                        except Exception:
                            print(str(tuple(r)))
                return
            elif d in ("postgres", "postgresql"):
                sql = text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = ANY(current_schemas(false)) AND tablename = :tbl
                """)
                for r in conn.execute(sql, {"tbl": tbl}).fetchall():
                    mp = getattr(r, "_mapping", None)
                    print(str(dict(mp)) if mp is not None else str(tuple(r)))
                return
            elif d == "mysql":
                sql = text(f"SHOW INDEX FROM {tbl}")
                for r in conn.execute(sql).fetchall():
                    mp = getattr(r, "_mapping", None)
                    print(str(dict(mp)) if mp is not None else str(tuple(r)))
                return
            elif d == "clickhouse":
                sql = text(f"SHOW INDEXES FROM {tbl}")
                for r in conn.execute(sql).fetchall():
                    mp = getattr(r, "_mapping", None)
                    print(str(dict(mp)) if mp is not None else str(tuple(r)))
                return
            else:
                print(f"[yellow]Unsupported dialect: {d}. Skipping.[/yellow]")
                return
        except Exception as exc:
            print(f"[yellow]Failed to read indexes for {tbl}: {exc}[/yellow]")
            return


@app.command(name="db-drop-indexes")
def db_drop_indexes(
    table: str = typer.Option("", help="Target table name (default: DW_TABLE setting)"),
    dialect: str = typer.Option("", help="Force dialect sqlite/mysql/postgres/clickhouse (default: WAREHOUSE_DIALECT)"),
    yes: bool = typer.Option(False, help="Confirm dropping recommended indexes"),
) -> None:
    """Drop the recommended indexes (use with caution)."""
    s = setup_cli_command()
    if not yes:
        print("[yellow]Preview only. Re-run with --yes to drop indexes.[/yellow]")
        return
    if not s.database_url:
        print("[red]DATABASE_URL not configured.[/red]")
        raise typer.Exit(code=1)

    from sqlalchemy import create_engine, text
    engine = create_engine(s.database_url)
    tbl = (table or s.dw_table)
    d = (dialect or s.warehouse_dialect or "sqlite").lower()

    stmts = []
    if d in ("sqlite", "mysql", "postgres", "postgresql"):
        stmts = [
            f"DROP INDEX IF EXISTS idx_month",
            f"DROP INDEX IF EXISTS idx_month_channel",
            f"DROP INDEX IF EXISTS idx_channel_user",
            f"DROP INDEX IF EXISTS idx_active",
        ]
        if d in ("mysql",):
            # MySQL requires table-qualified drop for non-unique? Keep generic here.
            pass
    elif d == "clickhouse":
        stmts = [
            f"ALTER TABLE {tbl} DROP INDEX IF EXISTS idx_month",
            f"ALTER TABLE {tbl} DROP INDEX IF EXISTS idx_month_channel",
            f"ALTER TABLE {tbl} DROP INDEX IF EXISTS idx_channel_user",
        ]
    else:
        print(f"[yellow]Unsupported dialect: {d}. Skipping.[/yellow]")
        return

    with engine.begin() as conn:
        for sql in stmts:
            try:
                conn.execute(text(sql))
                print(f"[green]Dropped:[/green] {sql}")
            except Exception as exc:
                print(f"[yellow]Skip or failed: {sql} -> {exc}[/yellow]")


@app.command()
def db_init(db_path: Path = typer.Option(None, help="SQLite DB file path")) -> None:
	"""Initialize a local SQLite DB with a demo table for validation."""
	setup_cli_command()
	s = load_settings()
	if db_path is None:
		db_path = Path(s.default_paths.get("db_path", "datainsight.db"))
	db_url = init_sqlite_min(db_path)
	print(f"[green]SQLite initialized:[/green] {db_url}")
	print("Add this to your .env to enable live validation:")
	print(f"DATABASE_URL={db_url}")


@app.command(name="db-init-dw-lite")
def db_init_dw_lite(db_path: Path = typer.Option(None, help="SQLite DB file path")) -> None:
	"""Initialize/widen local SQLite fact table with dimension columns and seed demo data.

	Creates/overwrites `dws_user_activity` with columns:
	- user_id TEXT, month TEXT, active INTEGER,
	- channel_code TEXT, device TEXT, region TEXT, user_level TEXT, app_version TEXT, campaign TEXT
	"""
	setup_cli_command()
	s = load_settings()
	if db_path is None:
		db_path = Path(s.default_paths.get("db_path", "datainsight.db"))
	db_url = init_sqlite_dw_lite(db_path)
	print(f"[green]SQLite widened and seeded:[/green] {db_url}")
	print("Now you can group by channel_code/device/region/user_level/app_version/campaign and 8 new dims: device_model, os_version, country, city, network_type, channel_subtype, ab_bucket, user_segment.")


@app.command(name="db-init-mysql")
def db_init_mysql(yes: bool = typer.Option(False, help="Confirm creating table and seeding data")) -> None:
	"""Initialize MySQL table and seed demo data using DATABASE_URL.

	Requires DATABASE_URL in .env (e.g., mysql+pymysql://user:pass@host:3306/datainsight?charset=utf8mb4).
	"""
	s = setup_cli_command()
	validate_command_params(require_confirmation=True, yes=yes, require_mysql=True, database_url=s.database_url)

	init_mysql_min(s.database_url)
	print("[green]MySQL initialized and seeded.[/green]")


@app.command(name="db-init-postgresql")
def db_init_postgresql(yes: bool = typer.Option(False, help="Confirm creating table and seeding data")) -> None:
	"""Initialize PostgreSQL table and seed demo data using DATABASE_URL.

	Requires DATABASE_URL in .env (e.g., postgresql://user:pass@host:5432/datainsight).
	"""
	s = setup_cli_command()
	validate_command_params(require_confirmation=True, yes=yes, require_postgresql=True, database_url=s.database_url)

	init_postgresql_dw(s.database_url)
	print("[green]PostgreSQL initialized and seeded.[/green]")


@app.command(name="db-init-clickhouse")
def db_init_clickhouse(yes: bool = typer.Option(False, help="Confirm creating table and seeding data")) -> None:
	"""Initialize ClickHouse table and seed demo data using DATABASE_URL.

	Requires DATABASE_URL in .env (e.g., clickhouse://user:pass@host:9000/datainsight).
	"""
	s = setup_cli_command()
	print("[yellow]ClickHouse initialization is not implemented yet. Skipping.[/yellow]")


@app.command()
def run(
	question: str = typer.Option(..., help="User question in natural language"),
	validate: bool = typer.Option(False, help="Validate generated SQL syntax & safety"),
	live: bool = typer.Option(False, help="If validate, also run EXPLAIN against DATABASE_URL"),
	execute: bool = typer.Option(False, help="Execute SQL if plan requires and DATABASE_URL available"),
	engine: str = typer.Option("", help="Orchestrator engine (default: llamaindex)"),
    json_out: bool = typer.Option(False, "--json", help="Print machine-readable JSON only"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors in output"),
) -> None:
	"""Run the agent pipeline for a given question."""
	s = setup_cli_command()
	log_command_start("run", question=question)
	# Use LlamaIndex engine
	eng = (engine or getattr(s, "orchestrator_engine", "llamaindex") or "llamaindex").lower()
	try:
		from datainsight_agent.orchestrator.li import build_pipeline as _build_li
		agent = _build_li()
		append_log_line("engine_selected", engine=eng)
	except Exception as _e:
		handle_command_error("run", _e, question=question)
	state = {"question": question}

	# Stream pipeline results
	final: dict = {}
	for values in agent.stream(state, stream_mode="values"):
		if isinstance(values, dict):
			final.update(values)


	plan = final.get("plan")
	sql = final.get("sql")
	ir = final.get("ir")

	# LlamaIndex pipeline execution

	# 使用统一的打印函数
	from datainsight_agent.cli_helpers import print_plan_ir_sql
	print_plan_ir_sql(final, s, validate, live, execute)

	# Handle different plan types
	handlers = {
		"clarify": lambda: handle_clarify_plan(final, question, s, validate, live, execute),
		"confirm_default_time": lambda: handle_confirm_default_time_plan(final, question, s, validate, live, execute),
	}
	
	if not sql and plan in handlers:
		success = handlers[plan]()
		log_command_end("run", success=success, plan=plan, have_sql=success)
	else:
		rows_count = handle_sql_execution(sql, s, validate, live, execute) if sql else None
		log_command_end("run", success=True, plan=plan, have_sql=bool(sql), executed=bool(execute and s.database_url), rows_count=rows_count)

	# Print timings if available
	if final.get("timings"):
		print_timings(final["timings"])

	response = final.get("response")
	if response:
		print(response)


@app.command()
def etl(source: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Path to RAGFlow output directory"), dry_run: bool = typer.Option(True, help="Do not write to stores"), yes: bool = typer.Option(False, help="Confirm potentially destructive writes")) -> None:
	"""Run ETL to populate KB stores from RAGFlow outputs."""
	s = setup_cli_command()
	append_log_line("etl_invoke", cmd="etl", source=str(source), dry_run=dry_run, yes=yes)
	run_ragflow_etl(source=source, yes=yes, dry_run=dry_run)
	print("[green]ETL completed (stub).[/green]")
	append_log_line("etl_done", cmd="etl", source=str(source), wrote=bool(yes and not dry_run))


@app.command(name="log-test")
def log_test(message: str = typer.Option("hello", help="Message to log")) -> None:
	"""Write a test log entry via project logging to verify file output."""
	s = setup_cli_command()
	# 使用配置化的日志文件名
	test_logging(message, Path(s.log_dir) / s.log_files.get("main", "datainsight_agent.log"))


@app.command(name="log-test-raw")
def log_test_raw(path: Path = typer.Option(None, help="Absolute or relative log file path"), message: str = typer.Option("hello", help="Message to write")) -> None:
	"""Write a test log entry using stdlib RotatingFileHandler directly (bypass structlog)."""
	s = load_settings()
	if path is None:
		path = Path(s.default_paths.get("log_path", "logs/datainsight_manual.log"))
	path.parent.mkdir(parents=True, exist_ok=True)
	import logging as _logging
	from logging.handlers import RotatingFileHandler as _RFH
	logger = _logging.getLogger("log_test_raw")
	for h in list(logger.handlers): logger.removeHandler(h)
	h = _RFH(str(path), maxBytes=5_000_000, backupCount=3)
	h.setFormatter(_logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
	logger.setLevel(_logging.INFO); logger.addHandler(h)
	logger.info("manual_test_raw %s", message)
	for hh in logger.handlers:
		try: hh.flush()
		except Exception: pass
	print("[green]Logged (raw).[/green] path=", path)


@app.command(name="db-seed-synthetic")
def db_seed_synthetic(
	rows: int = typer.Option(1000, help="Number of synthetic rows to generate"),
	months: int = typer.Option(3, help="Number of months to cover, counting back from start_month"),
	start_month: str = typer.Option("2025-09", help="Start month in YYYY-MM"),
	chunk_size: int = typer.Option(200, help="LLM generation batch size"),
	yes: bool = typer.Option(False, help="Confirm inserting into DATABASE_URL table"),
	output: Path = typer.Option(Path("") , help="If provided, write NDJSON to this path instead of DB"),
	use_llm: bool = typer.Option(True, help="Use model API to generate; fallback to local if unavailable"),
) -> None:
	"""Generate synthetic rows for dws_user_activity using LLM (or local fallback).

	- Safe by default: preview-only unless --yes or --output is provided
	- Requires DATABASE_URL and existing DW-lite schema when writing to DB
	- Columns: user_id, month (YYYY-MM), active (0/1), channel_code, device, region, user_level, app_version, campaign
	"""
	s = setup_cli_command()
	logger = get_logger("db_seed_synthetic")

	all_rows = generate_synthetic_data(rows, months, start_month, chunk_size, use_llm)

	# Preview summary
	print(f"[yellow]Prepared rows:[/yellow] {len(all_rows)}")
	for i, r in enumerate(all_rows[:5]):
		print(str(r))
	
	# Try to write NDJSON output first
	if write_ndjson_output(all_rows, output):
		return

	if not yes:
		print("[yellow]Preview only. Re-run with --yes to insert into DATABASE_URL, or use --output to write NDJSON.[/yellow]")
		return

	if not s.database_url:
		print("[red]DATABASE_URL not configured. Set it in .env or env var to enable insertion.[/red]")
		raise typer.Exit(code=1)

	# Insert into DB (requires DW-lite schema present)
	from sqlalchemy import create_engine, text
	engine = create_engine(s.database_url)
	# quick schema probe
	try:
		with engine.connect() as conn:
			res = conn.execute(text("PRAGMA table_info(dws_user_activity)"))
			cols = [row[1] for row in res.fetchall()]
	except Exception as exc:
		print(f"[red]Schema probe failed: {exc}[/red]")
		raise typer.Exit(code=1)

	required = {"user_id","month","active","channel_code","device","region","user_level","app_version","campaign"}
	if not required.issubset(set(cols)):
		print("[red]Target table schema mismatch. Please run: python -m datainsight_agent.cli db-init-dw-lite[/red]")
		raise typer.Exit(code=1)

	insert_sql = text(
		"""
		INSERT INTO dws_user_activity (user_id, month, active, channel_code, device, region, user_level, app_version, campaign)
		VALUES (:user_id, :month, :active, :channel_code, :device, :region, :user_level, :app_version, :campaign)
		"""
	)
	with engine.begin() as conn:
		conn.execute(insert_sql, all_rows)
	print(f"[green]Inserted rows:[/green] {len(all_rows)} -> {s.database_url}")


@app.command(name="rewrite")
def rewrite(
	question: str = typer.Option(..., help="Fuzzy user input in natural language"),
	top_k: int = typer.Option(5, help="Top-K KB entities to retrieve for RAG context"),
	show_prompt: bool = typer.Option(False, help="Print the constructed prompt and KB context"),
) -> None:
	"""Rewrite fuzzy query via LLM using lightweight RAG context, without executing downstream steps.

	Outputs:
	- Input question
	- RAG retrieval details (fuzzy metadata + optional HNSW vector)
	- Constructed prompt (optional) and the LLM JSON result for rewritten query
	"""
	s = load_settings()
	configure_logging(s)
	print("[blue]Input:[/blue]", question)
	append_log_line("rewrite_start", cmd="rewrite", question=question, top_k=top_k)

	# Load metadata KB (read JSON files directly; no local fuzzy index)
	entities = load_kb_entities()

	# No fuzzy matching
	fuzzy_top: List[tuple[float, KBEntity]] = []

	# RAG 2: vector search (if HNSW index available)
	vector_top: List[tuple[float, KBEntity]] = []
	vdir = Path(s.vector_index_dir)
	if vdir.exists() and entities:
		try:
			emb = EmbeddingModel()
			vec = emb.embed([question])[0]
			store = MilvusVectorStore(dim=len(vec), space=str(s.vector_space))
			pairs = store.search([vec], top_k=top_k)[0]
			id_to_entity = {e.id: e for e in entities}
			for _id, dist in pairs:
				ent = id_to_entity.get(_id)
				if ent:
					vector_top.append((float(dist), ent))
		except Exception:
			pass

	# Print RAG details (vector only)
	uniq_ids: list[str] = []
	_seen_ids = set()
	for _, e in vector_top:
		if e.id in _seen_ids:
			continue
		_seen_ids.add(e.id)
		uniq_ids.append(e.id)
	print(f"[cyan]RAG - vector (HNSW) matches:[/cyan] {len(uniq_ids)}")
	if show_prompt and vector_top:
		print("[cyan]RAG - vector (HNSW) top matches:[/cyan]")
		for dist, e in vector_top:
			print(f"dist={dist:.4f} id={e.id} name={e.canonical_name} type={e.type}")

	# Build KB context lines for rewrite prompt (dedup by id, prefer fuzzy ordering)
	seen = set()
	context_lines: List[str] = []
	for _, e in fuzzy_top + vector_top:
		if e.id in seen:
				continue
		seen.add(e.id)
		ds_str = ""
		if e.how and e.how.data_source:
			ds = e.how.data_source
			ds_str = f" table={ds.table}, column={ds.column}"
		aliases = "|".join(e.aliases)
		context_lines.append(f"id={e.id}, name={e.canonical_name}, aliases={aliases}, type={e.type}{ds_str}")
	kb_context = "\n".join(context_lines)

	# LLM rewrite: centralized prompt
	rewrite_prompt = q2q_prompt(kb_context, question)
	rewrite_json: dict | None = None
	try:
		client = QwenClient(s)
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
	try:
		got = rewrite_json if rewrite_json is not None else resp
		append_log_line("rewrite_end", cmd="rewrite", ok=bool(rewrite_json), result=str(got)[:500])
	except Exception:
		pass


@app.command(name="ir-run")
def ir_run(
	metric: str = typer.Option(..., help="Metric canonical name or alias, e.g. 月活/MAU/UV/PV"),
	group_by: str = typer.Option("", help="Comma-separated group-by columns, e.g. device,channel_code"),
	month: str = typer.Option("", help="Optional month filter YYYY-MM"),
	validate: bool = typer.Option(True, help="Validate generated SQL"),
	live: bool = typer.Option(True, help="If validate, also run EXPLAIN against DATABASE_URL"),
	execute: bool = typer.Option(True, help="Execute SQL if DATABASE_URL available"),
) -> None:
	"""Build IR manually in a metadata-driven way and generate SQL, then validate/execute."""
	s = setup_cli_command()
	append_log_line("ir_run_start", cmd="ir-run", metric=metric, group_by=group_by, month=month)

	try:
		ir = build_ir_from_metric(metric, group_by, month, s)
	except ValueError as e:
		print(f"[red]{e}[/red]")
		append_log_line("ir_run_end", cmd="ir-run", ok=False, error="metric_not_found")
		return

	sql = SQLGenerator().generate(ir)
	print("[cyan]Generated SQL:[/cyan]")
	print(sql)

	if validate:
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
	if execute and s.database_url:
		from datainsight_agent.services.core.sql_executor import SQLExecutor
		rows = SQLExecutor(s).execute(sql, limit=10)
		rows_count = len(rows)
		print("[green]Rows (up to 10):[/green]")
		for r in rows:
			print(r)

	append_log_line("ir_run_end", cmd="ir-run", ok=True, rows_count=rows_count)


@app.command(name="timings")
def timings(
	question: str = typer.Option(..., help="Fuzzy question to measure node timings"),
	no_llm: bool = typer.Option(False, help="Disable external LLM for deconstruct timing"),
	no_clear_cache: bool = typer.Option(False, help="Do not clear concepts cache before run"),
) -> None:
	"""Run the agent pipeline sequentially and print per-node timings (LlamaIndex)."""
	s = load_settings()
	configure_logging(s)
	from datainsight_agent.orchestrator.li import build_pipeline as _build_li
	agent = _build_li()
	state: dict = {"question": question}
	final: dict = {}
	for values in agent.stream(state, stream_mode="values"):
		if isinstance(values, dict):
			final.update(values)
	state = final
	# Print timings (unified)
	_timings = state.get("timings") or []
	print_timings(_timings)


@app.command(name="metrics-index")
def metrics_index(
    rebuild: bool = typer.Option(True, help="Rebuild the metric vector index"),
    show_stats: bool = typer.Option(True, help="Show basic index stats after build"),
):
    """Build/rebuild the metric vector index (HNSW) from metadata metrics."""
    s = load_settings()
    configure_logging(s)
    target = s.metric_index_dir
    # Rebuild by simply running builder (it appends; so we clear dir when rebuild True)
    target_path = Path(target)
    if rebuild and target_path.exists():
        # remove existing files
        for p in target_path.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
    target_path.mkdir(parents=True, exist_ok=True)
    n = build_metric_index(metadata_dir="metadata", index_dir=target_path)
    print(f"[green]Metric index built:[/green] {n} vectors -> {target_path}")
    if show_stats:
        try:
            store = MilvusVectorStore(dim=int(s.vector_dim), space=str(s.vector_space))
            # crude count: read meta.jsonl lines
            meta = target_path / "meta.jsonl"
            cnt = 0
            if meta.exists():
                with meta.open("r", encoding="utf-8") as f:
                    for _ in f:
                        cnt += 1
            print(f"[blue]Index stats:[/blue] items={cnt}")
        except Exception:
            pass


@app.command(name="kb-index")
def kb_index(
    rebuild: bool = typer.Option(True, help="Rebuild the KB vector index"),
    show_stats: bool = typer.Option(True, help="Show basic index stats after build"),
):
    """Build/rebuild the KB vector index (HNSW) from metadata KB entities."""
    s = load_settings()
    configure_logging(s)
    target = Path("kb_vector_index")
    
    # Rebuild by simply running builder (it appends; so we clear dir when rebuild True)
    if rebuild and target.exists():
        # remove existing files
        for p in target.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
    
    n = build_kb_vector_index(metadata_dir="metadata", index_dir=target)
    print(f"[green]KB index built:[/green] {n} vectors -> {target}")
    if show_stats:
        try:
            # crude count: read meta.jsonl lines
            meta_file = target / "meta.jsonl"
            if meta_file.exists():
                count = len(meta_file.read_text().strip().split('\n'))
                print(f"[blue]Index stats:[/blue] items={count}")
        except Exception:
            pass


@app.command(name="sql-preview")
def sql_preview(
    question: str = typer.Option(..., help="User analytics question (Chinese or English)"),
    db: Path = typer.Option(None, help="SQLite DB for preview execution"),
    top_k: int = typer.Option(6, help="Top-K KB entries to include in prompt context"),
    json_out: bool = typer.Option(False, "--json", help="Print machine-readable JSON only"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors in output"),
) -> None:
	"""Generate one SQL via LLM prompt with strict constraints; if ambiguous time, return clarify JSON. No heuristic business fallback."""
	s = load_settings()
	configure_logging(s)
	if db is None:
		db = Path(s.default_paths.get("sqlite_path", "./datainsight.db"))
	import os as _os
	import sqlite3 as _sqlite3
	from typing import List, Tuple
	from datainsight_agent.services.llm import DeepseekClient
	from datainsight_agent.models.kb import KBEntity

	# Allowed columns: prefer config over probing
	if s.dw_allowed_columns_csv.strip():
		all_cols = [c.strip() for c in s.dw_allowed_columns_csv.split(",") if c.strip()]
	else:
		all_cols = probe_columns(str(db))
	allowed_columns = ", ".join(all_cols)
	kb_ctx = get_kb_context_for_sql_preview(question, top_k)
	start_m, end_m = get_latest_year_range(str(db))

	system = sql_preview_system()
	prompt = sql_preview_prompt(
		allowed_columns=allowed_columns,
		start_month=start_m,
		end_month=end_m,
		kb_context=kb_ctx,
		question=question,
		table_name=s.dw_table,
		time_column=s.dw_time_column,
	)

	# Try LLM only (no heuristic fallback)
	text: str = ""
	try:
		text = QwenClient(s).generate_sql(prompt, system=system)
	except Exception:
		text = ""
	text = (text or "").strip()
	low = text.lower().strip()

	# Unified printing via helper (no extra validation here)
	if json_out:
		print(_json.dumps({"plan": "sql_preview", "sql": text}, ensure_ascii=False))
	else:
		print_plan_ir_sql({"plan": "sql_preview", "sql": text}, settings=s, validate=False, live=False, execute=False)

	# Very light safety check
	if not low.startswith("select"):
		print("[yellow][WARN] Not a SELECT; skipping execution.[/yellow]")
		return
	if any(k in low for k in ["update ", "delete ", "insert ", "drop ", "alter ", " create "]):
		print("[yellow][WARN] Potentially unsafe statement; skipping execution.[/yellow]")
		return

	# Execute preview against local SQLite
	execute_sqlite_preview(text, str(db))


def _run_pipeline_with_overrides(
	question: str,
	metric_override: str = "",
	time_filter_override: str = "",
	validate: bool = False,
	live: bool = False,
	execute: bool = False,
) -> dict:
	"""Run pipeline once with optional Q2Q-style overrides for metric/time, return final state."""
	import os as _os
	s = load_settings()
	# If we provide overrides, disable LLM Q2Q and concept extraction to avoid network waits
	from datainsight_agent.cli_helpers import env_temporary as _envtmp
	_envmap = {}
	if metric_override or time_filter_override:
		_envmap = {"LLM_Q2Q_ENABLED": "0", "DECONSTRUCT_SKIP_CONCEPTS_WHEN_Q2Q": "1"}
	# Use LlamaIndex engine
	eng = (_os.getenv("ORCHESTRATOR_ENGINE", "llamaindex") or "llamaindex").lower()
	from datainsight_agent.orchestrator.li import build_pipeline as _build_li
	agent = _build_li()
	state: dict = {"question": question}
	q2q: dict = {}
	if metric_override:
		q2q["metric"] = [metric_override]
	if time_filter_override:
		q2q["time_filter"] = time_filter_override
	# 保留原始concepts，避免检索时concepts丢失
	if not q2q.get("concepts"):
		# 从问题中提取基础concepts
		from datainsight_agent.config.keyword_mappings import KB_KEYWORDS
		question_lower = question.lower()
		concepts = []
		for keyword in KB_KEYWORDS:
			if keyword in question_lower:
				concepts.append(keyword)
		if concepts:
			q2q["concepts"] = concepts
			# print(f"[DEBUG] _run_pipeline_with_overrides: 提取concepts={concepts}")
	if q2q:
		state["q2q"] = q2q
	final: dict = {}
	with _envtmp(_envmap):
		for values in agent.stream(state, stream_mode="values"):
			if isinstance(values, dict):
				final.update(values)
	# LlamaIndex execution
	# Validate/execute if requested（unified helper）
	if validate or (execute and s.database_url):
		final = validate_and_maybe_execute_inplace(final, settings=s, validate=validate, live=live, execute=execute)
	return final


@app.command(name="compare-tasks")
def compare_tasks(
	question: str = typer.Option(..., help="Base question in natural language"),
	metric_a: str = typer.Option("", help="Override metric for task A (e.g., MAU)"),
	metric_b: str = typer.Option("", help="Override metric for task B (e.g., UV)"),
	time_a: str = typer.Option("", help="Override time window for A as YYYY-MM,YYYY-MM"),
	time_b: str = typer.Option("", help="Override time window for B as YYYY-MM,YYYY-MM"),
	validate: bool = typer.Option(False, help="Validate generated SQL"),
	live: bool = typer.Option(False, help="If validate, also run EXPLAIN against DATABASE_URL"),
	execute: bool = typer.Option(False, help="Execute SQL if DATABASE_URL available"),
	workers: int = typer.Option(2, help="Max parallel workers, default 2"),
) -> None:
	"""Split one query into two parallel sub-tasks (e.g., two metrics or two time windows)."""
	s = setup_cli_command()
	jobs = [
		("A", dict(metric=metric_a.strip(), time=time_a.strip())),
		("B", dict(metric=metric_b.strip(), time=time_b.strip())),
	]
	res_map = run_parallel_tasks(jobs, _run_pipeline_with_overrides, 
		question=question, validate=validate, live=live, execute=execute, workers=workers)
	print_task_results(res_map, metric_a, metric_b, time_a, time_b)
	
	# Print timings for each task
	for tag in ["A", "B"]:
		res = res_map.get(tag) or {}
		_tt = res.get("timings") or []
		if _tt:
			print(f"\n[cyan]==== Task {tag} Timings ====[/cyan]")
			print_timings(_tt)


@app.command(name="observe")
def observe(
	question: str = typer.Option(..., help="User question in natural language"),
	top_k: int = typer.Option(6, help="Top-K KB entities to include in RAG context"),
	validate: bool = typer.Option(True, help="Validate generated SQL syntax & optionally run EXPLAIN"),
	live: bool = typer.Option(True, help="If validate, also run EXPLAIN against DATABASE_URL"),
	execute: bool = typer.Option(True, help="Execute SQL if DATABASE_URL available"),
	show_prompt: bool = typer.Option(False, help="Print the constructed prompt and KB context"),
	json_out: bool = typer.Option(False, "--json", help="Print machine-readable JSON only"),
	no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors in output"),
) -> None:
	"""End-to-end observation: RAG rewrite → plan/IR/SQL → validate/execute → timings in one run."""
	s = setup_cli_command()
	if not json_out:
		print("[blue]Input:[/blue]", question)
	append_log_line("observe_start", cmd="observe", question=question, top_k=top_k)

	# Phase 1: RAG rewrite using Q2QRewriter (with dynamic KB context)
	rewrite_json, resp = perform_q2q_rewrite(question, top_k, s, show_prompt)

	if isinstance(rewrite_json, dict):
		try:
			norm = normalize_time_filter(str(rewrite_json.get("time_filter") or ""), question)
			if norm:
				rewrite_json["time_filter"] = norm
				# 规范化成功则移除 clarify/ask，避免误触发
				rewrite_json.pop("clarify", None)
				rewrite_json.pop("ask", None)
		except Exception:
			pass

	# If Q2Q requires clarification OR time_filter missing/placeholder/invalid OR original question lacks explicit time,
	# ask only for time and continue
	def _needs_time_prompt(data: dict) -> bool:
		tf = str(data.get("time_filter") or "").strip()
		if data.get("clarify"):
			return True
		if tf == "" or tf.upper() == "YYYY-MM,YYYY-MM":
			return True
		import re as _re
		return _re.match(r"^\d{4}-\d{2},\d{4}-\d{2}$", tf) is None

	def _question_has_explicit_time(q: str) -> bool:
		import re as _re
		q = (q or "").strip()
		return _re.search(r"20\d{2}-\d{2}\s*(?:到|~|–|-|—|\.\.|,|，)\s*20\d{2}-\d{2}", q) is not None

	if isinstance(rewrite_json, dict) and _needs_time_prompt(rewrite_json):
		ask_msg = str(rewrite_json.get("ask") or "请补充时间范围（YYYY-MM,YYYY-MM）。")
		print(ask_msg)
		t_in: str = ask_time()
		import re as _re
		if not t_in or _re.match(r"^\d{4}-\d{2},\d{4}-\d{2}$", t_in.strip()) is None:
			append_log_line("observe_end", cmd="observe", plan="clarify", have_sql=False, ask=ask_msg)
			return
		# Preserve any metric/group_by provided by Q2Q; just inject time_filter
		existing_metric = list(rewrite_json.get("metric") or [])
		existing_gb = list(rewrite_json.get("group_by") or [])
		existing_concepts = list(rewrite_json.get("concepts") or [])
		print(f"[DEBUG] CLI重新构建q2q: 原始concepts={existing_concepts}")
		rewrite_json = {
			"rewritten_question": question,
			"metric": existing_metric,
			"group_by": existing_gb,
			"time_filter": t_in.strip(),
			"concepts": existing_concepts,
		}
		print(f"[DEBUG] CLI重新构建q2q: 新concepts={rewrite_json['concepts']}")
		print("[yellow]已接收时间范围，将继续执行。[/yellow]")

	# Phase 2: Run full pipeline (inject Q2Q result first to avoid fallback)
	from datainsight_agent.orchestrator.li import build_pipeline as _build_li
	agent = _build_li()
	state = {"question": question}
	if rewrite_json is not None and isinstance(rewrite_json, dict):
		try:
			state["q2q"] = rewrite_json
		except Exception:
			pass
	final: dict = {}
	for values in agent.stream(state, stream_mode="values"):
		if isinstance(values, dict):
			final.update(values)

	plan = final.get("plan")
	sql = final.get("sql")
	ir = final.get("ir")

	# LlamaIndex execution
	if json_out:
		payload = {k: v for k, v in final.items() if k in ("plan","ir","sql","warnings","suggestions","ir_validation","timings")}
		print(_json.dumps(payload, ensure_ascii=False))
	else:
		print_plan_ir_sql(final, settings=s, validate=validate, live=live, execute=execute)
	if not sql:
		append_log_line("observe_end", cmd="observe", plan=plan, have_sql=False)
	else:
		rows_count = None
		if execute and s.database_url:
			try:
				from datainsight_agent.services.core.sql_executor import SQLExecutor
				rows = SQLExecutor(s).execute(sql, limit=10)
				rows_count = len(rows)
			except Exception:
				rows_count = None
		append_log_line("observe_end", cmd="observe", plan=plan, have_sql=True, executed=bool(execute and s.database_url), rows_count=rows_count)

	# Phase 3: timings (unified)
	_timings = final.get("timings") or []
	if _timings and not json_out:
		print_timings(_timings)


@app.command()
def api(
	host: str = typer.Option("0.0.0.0", help="API服务器主机地址"),
	port: int = typer.Option(8000, help="API服务器端口"),
	reload: bool = typer.Option(False, help="是否启用热重载")
) -> None:
	"""启动API服务器"""
	import uvicorn
	from datainsight_agent.common.logging import get_logger
	
	logger = get_logger("api_cli")
	logger.info(f"启动API服务器: {host}:{port}")
	
	try:
		uvicorn.run(
			"datainsight_agent.api.app:app",
			host=host,
			port=port,
			reload=reload,
			log_level="info"
		)
	except KeyboardInterrupt:
		logger.info("API服务器已停止")
	except Exception as e:
		logger.error(f"API服务器启动失败: {str(e)}")
		raise typer.Exit(1)


# LlamaIndex 是唯一的编排引擎。

if __name__ == "__main__":
	app()