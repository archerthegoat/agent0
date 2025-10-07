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


class Q2QSystemPrompts:
	"""Q2Q系统提示词模板 - 集中管理所有硬编码的prompt内容"""
	
	@staticmethod
	def get_base_rules() -> str:
		"""基础时间解析规则"""
		# 动态时间：避免硬编码当前月份
		from datainsight_agent.services.parsers.time_filter_parser import TimeFilterParser
		current_month = TimeFilterParser.get_current_month()

		return f"""Extract time information from Chinese queries following exact patterns:

QUARTER (季度) - MUST output canonical format:
- "2025年第3季度" → type="quarter", value="2025年第3季度"
- "2025-Q3" → type="quarter", value="2025-Q3"  
- "2025年Q3" → type="quarter", value="2025年Q3"

RANGE (范围):
- "2025年8月到2025年9月" → type="range", value="2025-08,2025-09"
- "2025年8月至9月" → type="range", value="2025-08,2025-09"

SINGLE (单月):
- "2025年8月" → type="single", value="2025-08"
- "8月" → type="single", value="2025-08"

RELATIVE (相对):
- "最近2个月" → type="relative", value="last_2_months"
- "近3个月" → type="relative", value="last_3_months"
- "今年" → type="relative", value="this_year"

YEAR (年):
- "2025年" → type="year", value="2025"

CRITICAL: For quarters, preserve original Chinese format in value field!

DEFAULT TIME INFERENCE - CRITICAL for queries without explicit time:
- If no time expression found, infer default time based on query context:
  * "按渠道统计MAU" → type="single", value="{current_month}" (current month)
  * "按地区统计DAU" → type="single", value="{current_month}" (current month)  
  * "设备分析" → type="single", value="{current_month}" (current month)
  * "平台对比" → type="single", value="{current_month}" (current month)
  * Any statistical query without time → type="single", value="{current_month}"

IMPORTANT: Always provide a time_filter, never leave it as "none" for statistical queries!"""

	@staticmethod
	def get_default_time_inference() -> str:
		"""默认时间推断规则"""
		from datainsight_agent.services.parsers.time_filter_parser import TimeFilterParser
		current_month = TimeFilterParser.get_current_month()
		return f"""

DEFAULT TIME INFERENCE - Apply when no explicit time found:
- Statistical queries need default time scope
- Use current month "{current_month}" as default
- Never return time_filter as "none" for MAU/DAU/UV/PV queries"""

	@staticmethod
	def get_group_by_mapping() -> str:
		"""GROUP BY字段映射规则"""
		return """

GROUP BY FIELD MAPPING - CRITICAL for correct SQL generation:
- 按月份/按月 → ["month"] 
- 按地区/按区域 → ["region"]
- 按渠道/按平台 → ["channel"]
- 按设备类型/按设备 → ["device_type"]
- 按时段/按小时/各时段 → ["created_hour"]
- 按季度/各季度 → ["quarter"]
- 按年份/按年 → ["year"]
- 移动端和Web端/平台对比 → ["channel"]
- 设备分析/设备统计 → ["device_type"]

PLATFORM FIELD MAPPING - CRITICAL for platform analysis:
- 平台分析/平台统计/平台对比 → ["platform"]
- 按平台/平台维度 → ["platform"]
- 平台类型/平台分布 → ["platform"]
- 移动端和Web端/渠道对比 → ["channel"] (keep existing)

IMPORTANT: Use exact English field names, NOT Chinese or mixed names!"""

	@staticmethod
	def get_metric_standardization() -> str:
		"""指标标准化指导"""
		return """

METRIC STANDARDIZATION - CRITICAL for correct metric identification:
- Always use STANDARD metric names from RAG context
- If RAG context provides standard aliases (MAU, DAU, UV, PV), use them
- Convert Chinese metric expressions to standard English abbreviations
- NEVER use Chinese metric names in metric array

EXAMPLES:
- Input: "用户活跃度统计" + RAG context shows "MAU" → Output: metric=["MAU"]
- Input: "月活跃用户分析" + RAG context shows "MAU" → Output: metric=["MAU"]  
- Input: "独立访客" + RAG context shows "UV" → Output: metric=["UV"]
- Input: "页面访问" + RAG context shows "PV" → Output: metric=["PV"]

CRITICAL RULE: Always prioritize RAG context standard names over original Chinese terms!"""

	@staticmethod
	def get_quarter_specific_rules() -> str:
		"""季度特定规则"""
		return """
QUARTER SPECIFIC:
Q1 (第一季度) = "01,03" (Jan-Mar)
Q2 (第二季度) = "04,06" (Apr-Jun)  
Q3 (第三季度) = "07,09" (Jul-Sep)
Q4 (第四季度) = "10,12" (Oct-Dec)

CRITICAL SEMANTIC ANALYSIS:
- For "第X季度指标汇总" (quarter summary): Do NOT add group_by
- For "各季度指标对比" (quarter comparison): Add group_by=["quarter"]
- For "季度内趋势分析" (quarter trend): Add group_by=["month"]

EXAMPLES:
- "2025年第二季度的MAU和UV对比" → NO group_by (quarter summary)
- "2025年各季度的UV对比" → group_by=["quarter"] (quarter comparison)
- "第3季度UV趋势" → group_by=["month"] (quarter trend)

CRITICAL: For quarter analysis queries like "第3季度UV趋势":
- Use time_filter with quarter range (e.g., "2025-07,2025-09")
- Do NOT add group_by=["month"] - this creates monthly breakdown instead of quarter summary
- Use aggregation without grouping for quarter totals
- Only add group_by=["quarter"] if explicitly asking for quarter comparison"""

	@staticmethod
	def get_relative_time_mapping() -> str:
		"""相对时间映射"""
		from datainsight_agent.services.parsers.time_filter_parser import TimeFilterParser
		m = TimeFilterParser.get_relative_time_mapping()
		return f"""
RELATIVE TIME MAPPING:
- 最近2个月 = "last_2_months" (format as range)
- 今年 = "{m['今年']}"
- 去年 = "{m['去年']}" 
- 本月 = "{m['本月']}"
- 上月 = "{m['上月']}""" 

	@staticmethod
	def get_trend_analysis_rules() -> str:
		"""趋势分析规则"""
		return """
TREND ANALYSIS: 
- For monthly trends: Add group_by=["month"] 
- For quarterly trends: Do NOT add group_by=["month"] - use aggregation instead
- For yearly trends: Add group_by=["year"]
- For quarter analysis queries: Use aggregation without grouping"""

	@staticmethod
	def build_system_prompt(query_type: dict) -> str:
		"""根据查询类型动态构建系统提示词"""
		base_rules = Q2QSystemPrompts.get_base_rules()
		default_time_inference = Q2QSystemPrompts.get_default_time_inference()
		group_by_mapping = Q2QSystemPrompts.get_group_by_mapping()
		metric_standardization = Q2QSystemPrompts.get_metric_standardization()
		
		# 按需添加特定指导
		focused_rules = ""
		
		if query_type.get('has_quarter', False):
			focused_rules += Q2QSystemPrompts.get_quarter_specific_rules()
		
		if query_type.get('has_relative_time', False):
			focused_rules += Q2QSystemPrompts.get_relative_time_mapping()
		
		if query_type.get('has_trend', False):
			focused_rules += Q2QSystemPrompts.get_trend_analysis_rules()
		
		return f"{base_rules}{default_time_inference}{group_by_mapping}{metric_standardization}{focused_rules}\nAlways set confidence >= 0.8 for clear expressions."



