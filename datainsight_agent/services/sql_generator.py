from __future__ import annotations

from typing import List, Optional
from datainsight_agent.config.settings import load_settings
from datainsight_agent.adapters.factory import DatabaseAdapterFactory

from datainsight_agent.models.ir import SemanticQueryIR


class SQLGenerator:
	"""Naive SQL generator from IR.

	This is a placeholder focusing on structure; not production-safe.
	"""

	def __init__(self, database_url: Optional[str] = None):
		"""Initialize SQL generator with database URL for dialect detection.
		
		Args:
			database_url: Database connection URL for dialect detection
		"""
		self.database_url = database_url
		self._adapter = None
		if database_url:
			try:
				self._adapter = DatabaseAdapterFactory.create_adapter(database_url)
			except Exception:
				# Fallback to default dialect if adapter creation fails
				pass

	def _get_dialect(self) -> str:
		"""Get the database dialect."""
		if self._adapter:
			return self._adapter.dialect
		
		# Fallback to settings
		s = load_settings()
		return s.warehouse_dialect.lower()

	def generate(self, ir: SemanticQueryIR, default_table: str = "") -> str:
		# 检查是否需要归因分析SQL
		if ir.attribution_analysis:
			return self._generate_attribution_sql(ir, default_table)
		
		return self._generate_standard_sql(ir, default_table)
	
	def _render_filter(self, field: str, operator: str, value: str, time_type: str = None, time_unit: str = None) -> str:
		"""渲染过滤条件"""
		op = (operator or "=").upper().strip()
		val = value if value is not None else ""
		
		# 时间过滤的特殊处理
		if time_type and time_unit:
			return self._render_time_filter_internal(field, op, val, time_type, time_unit)
		
		# 原有的非时间过滤逻辑
		if op == "BETWEEN":
			parts = [p.strip() for p in val.split(",", 1)]
			if len(parts) == 2:
				return f"{field} BETWEEN '{parts[0]}' AND '{parts[1]}'"
			return f"{field} = '{val}'"
		if op == "IN":
			items = [p.strip() for p in val.split(",") if p.strip()]
			joined = ",".join([f"'{it}'" for it in items])
			return f"{field} IN ({joined})" if items else f"{field} IS NULL"
		if op == "LIKE_ANY":
			patterns = [p.strip() for p in val.split(",") if p.strip()]
			if not patterns:
				return f"{field} IS NULL"
			if len(patterns) == 1:
				return f"{field} LIKE '{patterns[0]}'"
			return "(" + " OR ".join([f"{field} LIKE '{pat}'" for pat in patterns]) + ")"
		return f"{field} {op} '{val}'"
	
	def _render_time_filter_internal(self, field: str, operator: str, value: str, time_type: str, time_unit: str) -> str:
		"""渲染时间过滤条件，支持多种时间表达式和数据库方言"""
		val = value.strip()
		dialect = self._get_dialect()
		
		if time_type == "single":
			# 单个月份/日期：month = '2024-05'
			return f"{field} = '{val}'"
		
		elif time_type == "range":
			# 时间范围：month BETWEEN '2024-01' AND '2024-12'
			if "," in val:
				parts = [p.strip() for p in val.split(",", 1)]
				if len(parts) == 2:
					if dialect == "postgresql":
						# PostgreSQL时间函数
						if time_unit == "month":
							return f"DATE_TRUNC('month', {field}) BETWEEN '{parts[0]}' AND '{parts[1]}'"
					elif dialect == "clickhouse":
						# ClickHouse时间函数
						if time_unit == "month":
							return f"toStartOfMonth({field}) BETWEEN '{parts[0]}' AND '{parts[1]}'"
					else:
						# 标准SQL
						return f"{field} BETWEEN '{parts[0]}' AND '{parts[1]}'"
			return f"{field} = '{val}'"
		
		elif time_type == "relative":
			# 相对时间：近N个月
			if "近" in val and "个月" in val:
				try:
					num = int(val.replace("近", "").replace("个月", ""))
					if dialect == "postgresql":
						return f"{field} >= CURRENT_DATE - INTERVAL '{num} months'"
					elif dialect == "clickhouse":
						return f"{field} >= today() - INTERVAL {num} MONTH"
					else:
						return f"{field} >= date('now', '-{num} months')"
				except ValueError:
					pass
			return f"{field} = '{val}'"
		
		elif time_type == "list":
			# 时间列表：month IN ('2024-01', '2024-02', '2024-03')
			if "," in val:
				items = [p.strip() for p in val.split(",") if p.strip()]
				joined = ",".join([f"'{it}'" for it in items])
				return f"{field} IN ({joined})"
			return f"{field} = '{val}'"
		
		else:
			# 默认处理
			return f"{field} = '{val}'"
	
	def _generate_standard_sql(self, ir: SemanticQueryIR, default_table: str = "") -> str:
		select_parts: List[str] = []
		group_by_parts: List[str] = []
		if not default_table:
			# use configured table if not provided
			s = load_settings()
			# 使用配置化的表名
			default_table = s.dw_table or "dws_user_activity_monthly"

		# 构建 SELECT 子句
		for agg in ir.aggregations:
			if agg.field:
				select_parts.append(f"{agg.function}({agg.field}) AS {agg.alias or agg.function.lower()}")
		
		# 构建 GROUP BY 子句
		for field in ir.group_by:
			group_by_parts.append(field)
			if field not in [p.split(" AS ")[0] for p in select_parts]:
				select_parts.append(field)

		# 构建 WHERE 子句
		where_conditions = []
		for filter_obj in ir.filters:
			where_conditions.append(self._render_filter(
				filter_obj.field, filter_obj.operator, filter_obj.value,
				filter_obj.time_type, filter_obj.time_unit
			))

		# 构建 JOIN 子句
		join_clauses = []
		for join_obj in ir.joins:
			join_clause = f"{join_obj.join_type.upper()} JOIN {join_obj.right_table} ON "
			join_conditions = []
			for left_field, right_field in join_obj.on.items():
				join_conditions.append(f"{left_field} = {join_obj.right_table}.{right_field}")
			join_clause += " AND ".join(join_conditions)
			join_clauses.append(join_clause)

		# 组装 SQL
		select_clause = ", ".join(select_parts) if select_parts else "*"
		where_clause = " AND ".join(where_conditions) if where_conditions else ""
		group_clause = ", ".join(group_by_parts) if group_by_parts else ""
		order_clause = ", ".join(ir.order_by) if ir.order_by else ""

		sql = f"SELECT {select_clause} FROM {default_table}"
		if join_clauses:
			sql += " " + " ".join(join_clauses)
		if where_clause:
			sql += f" WHERE {where_clause}"
		if group_clause:
			sql += f" GROUP BY {group_clause}"
		if order_clause:
			sql += f" ORDER BY {order_clause}"
		if ir.limit:
			sql += f" LIMIT {ir.limit}"
		return sql
	
	def _generate_attribution_sql(self, ir: SemanticQueryIR, default_table: str = "") -> str:
		"""生成归因分析SQL"""
		attribution = ir.attribution_analysis
		
		if not default_table:
			s = load_settings()
			default_table = s.dw_table or "dws_user_activity_monthly"
		
		# 构建基础查询
		select_parts = []
		group_by_parts = []
		
		# 添加时间字段
		select_parts.append("month")
		group_by_parts.append("month")
		
		# 添加分析维度
		for dimension in attribution.dimensions:
			if dimension in ir.group_by:
				select_parts.append(dimension)
				group_by_parts.append(dimension)
		
		# 添加指标聚合
		for agg in ir.aggregations:
			if agg.field:
				select_parts.append(f"{agg.function}({agg.field}) AS {agg.alias or agg.function.lower()}")
		
		# 构建WHERE条件
		where_conditions = []
		
		# 添加基础过滤条件
		for filter_obj in ir.filters:
			where_conditions.append(self._render_filter(
				filter_obj.field, filter_obj.operator, filter_obj.value,
				filter_obj.time_type, filter_obj.time_unit
			))
		
		# 添加归因分析的时间范围
		if attribution.base_period and attribution.comparison_period:
			# 解析季度到月份范围
			base_months = self._parse_quarter_to_months(attribution.base_period)
			comparison_months = self._parse_quarter_to_months(attribution.comparison_period)
			
			all_months = base_months + comparison_months
			if all_months:
				month_list = "', '".join(all_months)
				where_conditions.append(f"month IN ('{month_list}')")
		
		# 构建SQL
		select_clause = ", ".join(select_parts)
		where_clause = " AND ".join(where_conditions) if where_conditions else ""
		group_clause = ", ".join(group_by_parts) if group_by_parts else ""
		
		sql = f"SELECT {select_clause} FROM {default_table}"
		if where_clause:
			sql += f" WHERE {where_clause}"
		if group_clause:
			sql += f" GROUP BY {group_clause}"
		
		# 添加排序
		sql += " ORDER BY month"
		for dimension in attribution.dimensions:
			if dimension in ir.group_by:
				sql += f", {dimension}"
		
		return sql
	
	def _parse_quarter_to_months(self, quarter: str) -> List[str]:
		"""解析季度到月份列表"""
		if not quarter or "-Q" not in quarter:
			return []
		
		try:
			year, q = quarter.split("-Q")
			year = int(year)
			quarter_num = int(q)
			
			if quarter_num == 1:
				return [f"{year}-01", f"{year}-02", f"{year}-03"]
			elif quarter_num == 2:
				return [f"{year}-04", f"{year}-05", f"{year}-06"]
			elif quarter_num == 3:
				return [f"{year}-07", f"{year}-08", f"{year}-09"]
			elif quarter_num == 4:
				return [f"{year}-10", f"{year}-11", f"{year}-12"]
		except (ValueError, IndexError):
			pass
		
		return []