from __future__ import annotations

"""Centralized LLM prompt templates.

Keep all strings and template builders here to avoid scatter and hardcoding
across CLI or service modules.
"""


def q2q_prompt(kb_context: str, question: str) -> str:
	"""Prompt for Q2Q rewrite with structured outputs.

	Returns a single string prompt. The LLM should output a compact JSON object:
	{
	  rewritten_question,
	  metric: string[],
	  group_by: string[],
	  time_filter: string (e.g., "YYYY-MM,YYYY-MM"),
	  concepts: string[],
	  clarify: boolean,
	  ask: string
	}
	"""
	from datainsight_agent.config.settings import load_settings
	s = load_settings()
	table_name = s.dw_table
	time_column = s.dw_time_column

	# 基础约束（不包含硬编码的列名和映射）
	constraints = (
		"STRICT CONSTRAINTS:\n"
		f"- Target table: {table_name}.\n"
		f"- Time column: {time_column}.\n"
		"- Use exact column names from the knowledge context below.\n"
		"- Output MUST be pure JSON. No extra text.\n"
		"- Time normalization rules: if the question contains a single month 'YYYY-MM', set time_filter to 'YYYY-MM,YYYY-MM'.\n"
		"- If two months are present with separators (到/至/~/–/-/—/.. /, /，), map to 'start,end'.\n"
		"- Do NOT return clarify when time can be deterministically derived from the question using the rules above.\n"
		"- Only return clarify when BOTH metric and time cannot be determined.\n"
	)

	return (
		"You are a precise analytics rewriter. Rewrite the user's fuzzy question into an explicit analytics task in Chinese.\n"
		+ constraints +
		"Return ONLY a compact JSON with keys: rewritten_question, metric (array), group_by (array), time_filter (string like 'YYYY-MM,YYYY-MM'), concepts (array).\n"
		"If insufficient info (e.g., missing metric or time), return {\"clarify\": true, \"ask\": \"请补充时间范围（YYYY-MM,YYYY-MM）或指标\"}.\n\n"
		"Knowledge (for context):\n" + (kb_context or "") + "\n\nQuestion: " + (question or "")
	)


def sql_preview_system() -> str:
	"""System message for deterministic SQL-only generation."""
	return (
		'You are a precise SQLite SQL generator. Return ONLY one valid SELECT statement, or when the time requirement is ambiguous, return a JSON clarify object of the form {"clarify": true, "ask": "请确认时间范围(例如: 2025-01..2025-12/近12个月/某个月)"}.'
	)


def sql_preview_prompt(
	allowed_columns: str,
	start_month: str,
	end_month: str,
	kb_context: str,
	question: str,
	table_name: str = None,
	time_column: str = None,
) -> str:
	"""Prompt for constrained SQLite SELECT generation.

	The model must emit a single SELECT or an explicit clarify JSON.
	"""
	# 使用配置化的表名和时间列
	from datainsight_agent.config.settings import load_settings
	s = load_settings()
	actual_table_name = table_name or s.dw_table
	actual_time_column = time_column or s.dw_time_column
	
	return (
		"Generate one SQLite SELECT for the user's analytics question under STRICT constraints:\n"
		f"- Only use table {actual_table_name}; no JOIN/CTE/DDL/DML.\n"
		f"- Allowed columns: {allowed_columns}. Use exact names; do NOT invent fields.\n"
		f"- If the question specifies an explicit time range (e.g., 2025-01..2025-12), apply it using column {actual_time_column}.\n"
		"- If the time requirement is ambiguous or missing, return {\"clarify\": true, \"ask\": \"请确认时间范围(例如: 2025-01..2025-12/近12个月/某个月)\"}.\n"
		"- Choose GROUP BY columns only from the allowed set.\n"
		"- Output a single SELECT or the clarify JSON. No comments.\n\n"
		"Knowledge (for context):\n" + (kb_context or "") + "\n\nQuestion: " + (question or "")
	)


