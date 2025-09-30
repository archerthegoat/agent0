"""
LEGACY: Original SQL generator used by the pipeline.

Bridged by the component `components.sql_generator.SQLGenerator_component`.
Prefer using the component interface in new code.
"""
from __future__ import annotations

from typing import List, Optional
from datainsight_agent.config.settings import load_settings
from datainsight_agent.models.ir import SemanticQueryIR


class SQLGenerator:
    """Naive SQL generator from IR."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url

    def generate(self, ir: SemanticQueryIR, default_table: str = "") -> str:
        if ir.attribution_analysis:
            return self._generate_attribution_sql(ir, default_table)
        return self._generate_standard_sql(ir, default_table)

    def _generate_standard_sql(self, ir: SemanticQueryIR, default_table: str = "") -> str:
        select_parts: List[str] = []
        group_by_parts: List[str] = []
        select_fields_tracked: set = set()
        
        # 从第一个聚合中获取表映射信息
        table_mapping = {}
        time_field = 'month'
        if ir.aggregations and ir.aggregations[0].table_mapping:
            table_mapping = ir.aggregations[0].table_mapping
            time_field = table_mapping.get('time_field', 'month')
            default_table = table_mapping.get('table_name', default_table)
        
        if not default_table:
            s = load_settings()
            default_table = s.dw_table or "dws_user_activity"

        # 处理聚合函数
        for aggregation in ir.aggregations:
            function = aggregation.function.upper()
            field = aggregation.field or "user_id"
            alias = aggregation.alias or aggregation.function.lower()
            
            if function == "COUNT":
                agg_expr = f"{function}({field})"
            elif function == "SUM":
                agg_expr = f"SUM({field})"
            elif function == "AVG":
                agg_expr = f"AVG({field})"
            elif function == "MAX":
                agg_expr = f"MAX({field})"
            elif function == "MIN":
                agg_expr = f"MIN({field})"
            else:
                agg_expr = f"{function}({field})"
            
            agg_select_part = f"{agg_expr} AS {alias}"
            select_parts.append(agg_select_part)
            select_fields_tracked.add(alias.lower())

        # 处理GROUP BY字段
        for field in ir.group_by:
            mapped_field = self._map_field(field, time_field)
            
            if mapped_field == 'year':
                if time_field == 'date':
                    year_field = "YEAR(date)"
                else:
                    year_field = "SUBSTR(month, 1, 4)"
                group_by_parts.append(year_field)
                # 避免重复添加：只当字段未在SELECT中存在时才添加
                if 'year' not in select_fields_tracked:
                    select_parts.append(f"{year_field} AS year")
                    select_fields_tracked.add('year')
            elif mapped_field == 'month' and time_field == 'date':
                month_field = "DATE_FORMAT(date, '%Y-%m')"
                group_by_parts.append(month_field)
                if 'month' not in select_fields_tracked:
                    select_parts.append(f"{month_field} AS month")
                    select_fields_tracked.add('month')
            else:
                if mapped_field and mapped_field.lower() not in select_fields_tracked:
                    group_by_parts.append(mapped_field)
                    # 对于CASE表达式，需要添加合适的别名
                    if 'CASE' in mapped_field.upper():
                        # 根据字段名确定别名
                        if 'quarter' in field.lower():
                            select_alias = 'quarter'
                        elif 'year' in field.lower():
                            select_alias = 'year'
                        else:
                            select_alias = 'computed_field'
                        select_parts.append(f"{mapped_field} AS {select_alias}")
                        select_fields_tracked.add(select_alias.lower())
                    else:
                        select_parts.append(mapped_field)
                        select_fields_tracked.add(mapped_field.lower())

        # 构建WHERE子句
        where_conditions = []
        for filter_obj in ir.filters:
            where_conditions.append(self._render_filter(
                filter_obj.field, filter_obj.operator, filter_obj.value,
                filter_obj.time_type, filter_obj.time_unit
            ))

        # 处理ORDER BY字段映射，直接使用SELECT中的别名
        order_by_parts = []
        
        # 为CASE表达式建立别名映射表
        case_aliases = {}
        for i, select_part in enumerate(select_parts):
            if 'CASE' in select_part.upper() and 'AS' in select_part:
                # 提取别名，格式: CASE ... END AS alias
                alias_part = select_part.split(' AS ')[-1]
                case_aliases[f"CASE_EXPR_{i}"] = alias_part.strip()
        
        for order_field in ir.order_by:
            mapped_order_field = self._map_field(order_field, time_field)
            
            # 检查是否为复杂CASE表达式
            if 'CASE' in mapped_order_field.upper():
                # 优先检查是否与SELECT中的CASE表达式匹配
                matched_alias = None
                for select_part in select_parts:
                    if mapped_order_field.strip() in select_part.replace(' ', '').replace('\n', ''):
                        # 找到对应的别名
                        if 'AS' in select_part:
                            matched_alias = select_part.split('AS')[-1].strip()
                            break
                
                if matched_alias:
                    order_by_parts.append(matched_alias)
                else:
                    # 回退到字段名匹配
                    if 'quarter' in order_field.lower():
                        order_by_parts.append('quarter')
                    elif 'year' in order_field.lower():
                        order_by_parts.append('year')
                    else:
                        order_by_parts.append('computed_field')
            else:
                # 普通字段直接使用映射后的字段名
                order_by_parts.append(mapped_order_field)
        
        # 组装SQL
        select_clause = ", ".join(select_parts) if select_parts else "*"
        where_clause = " AND ".join(where_conditions) if where_conditions else ""
        group_clause = ", ".join(group_by_parts) if group_by_parts else ""
        order_clause = ", ".join(order_by_parts) if order_by_parts else ""

        sql = f"SELECT {select_clause} FROM {default_table}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if group_clause:
            sql += f" GROUP BY {group_clause}"
        
        # 智能ORDER BY：为多维度查询添加排序
        if not order_clause and group_clause:
            group_fields = group_clause.split(", ")
            if len(group_fields) > 1:
                # 多维度查询：按所有分组字段排序
                order_clause = ", ".join(group_fields)
            elif len(group_fields) == 1:
                # 单维度查询：按分组字段排序
                order_clause = group_fields[0]
        
        if order_clause:
            sql += f" ORDER BY {order_clause}"
        if ir.limit:
            sql += f" LIMIT {ir.limit}"
        
        return sql

    def _map_field(self, field: str, time_field: str) -> str:
        """字段映射和验证"""
        # 中文字段名到英文字段名的映射
        chinese_field_mapping = {
            '渠道': 'channel',
            '地区': 'region', 
            '设备类型': 'device_type',
            '平台': 'platform',
            '季度': 'quarter',
            '时段': 'created_hour',
            '小时': 'created_hour'
        }
        
        # 英文字段别名到实际字段的映射
        english_field_mapping = {
            'hour': 'created_hour',  # test_024问题
            'year_hour': 'created_hour',
            'device': 'device_type',  # 设备字段映射
            'channel_code': 'channel',  # 渠道字段映射
            'region_code': 'region',  # 地区字段映射
            'platform_type': 'platform',  # 平台字段映射
            'year': 'year',  # year字段映射
            'year': 'year',  # year字段映射
            'time_field': 'month',  # 时间字段映射（使用month而不是date）
            'page_views': 'page_view_id',  # PV字段映射
            'pageviews': 'page_view_id',  # PV字段映射
        }
        
        # 基础时间字段映射
        time_field_mapping = {
            'date': time_field,
            'day': time_field,
            'time_period': time_field,
        }
        
        # 优先处理中文字段映射
        if field in chinese_field_mapping:
            return chinese_field_mapping[field]
        
        # 处理英文字段别名映射
        if field in english_field_mapping:
            return english_field_mapping[field]
        
        # 处理时间字段映射
        if field in time_field_mapping:
            return time_field_mapping[field]
        
        # 处理复杂字段表达式（CASE表达式）
        complex_field_mapping = {
            'quarter': """CASE 
                WHEN month BETWEEN '2025-01' AND '2025-03' THEN 'Q1'
                WHEN month BETWEEN '2025-04' AND '2025-06' THEN 'Q2'
                WHEN month BETWEEN '2025-07' AND '2025-09' THEN 'Q3'
                WHEN month BETWEEN '2025-10' AND '2025-12' THEN 'Q4'
            END""",
            'year_category': f'SUBSTRING({time_field}, 1, 4)',
            'year_period': f'SUBSTRING({time_field}, 1, 4)',
        }
        
        if field in complex_field_mapping:
            return complex_field_mapping[field]
        
        # 直接返回英文字段名
        return field

    def _render_filter(self, field: str, operator: str, value: str, time_type: str = None, time_unit: str = None) -> str:
        """渲染过滤条件"""
        op = (operator or "=").upper().strip()
        val = value if value is not None else ""
        
        if time_type and time_unit:
            return self._render_time_filter_internal(field, op, val, time_type, time_unit)
        
        if op == "BETWEEN":
            parts = [p.strip() for p in val.split(",", 1)]
            if len(parts) == 2:
                if parts[0] == parts[1]:
                    return f"{field} = '{parts[0]}'"
                return f"{field} BETWEEN '{parts[0]}' AND '{parts[1]}'"
            return f"{field} = '{val}'"
        elif op == "IN":
            items = [p.strip() for p in val.split(",") if p.strip()]
            joined = ",".join([f"'{it}'" for it in items])
            return f"{field} IN ({joined})" if items else f"{field} IS NULL"
        elif op == "LIKE_ANY":
            patterns = [p.strip() for p in val.split(",") if p.strip()]
            if not patterns:
                return f"{field} IS NULL"
            if len(patterns) == 1:
                return f"{field} LIKE '{patterns[0]}'"
            return "(" + " OR ".join([f"{field} LIKE '{pat}'" for pat in patterns]) + ")"
        else:
            return f"{field} {op} '{val}'"

    def _render_time_filter_internal(self, field: str, operator: str, value: str, time_type: str, time_unit: str) -> str:
        """渲染时间过滤条件"""
        val = value.strip()
        
        if field == 'date':
            if time_type == "single":
                if len(val) == 7 and val[4] == '-':
                    val = f"{val}-01"
                return f"{field} = '{val}'"
            elif time_type == "range":
                if "," in val:
                    parts = [p.strip() for p in val.split(",", 1)]
                    if len(parts) == 2:
                        start_month, end_month = parts
                        start_date = f"{start_month}-01"
                        end_date = f"{end_month}-31"
                        return f"{field} BETWEEN '{start_date}' AND '{end_date}'"
                return f"{field} = '{val}'"
            elif time_type == "relative":
                if "近" in val and "个月" in val:
                    try:
                        num = int(val.replace("近", "").replace("个月", ""))
                        return f"{field} >= date('now', '-{num} months')"
                    except ValueError:
                        pass
                return f"{field} = '{val}'"
            elif time_type == "list":
                if "," in val:
                    items = [p.strip() for p in val.split(",") if p.strip()]
                    joined = ",".join([f"'{it}'" for it in items])
                    return f"{field} IN ({joined})"
                return f"{field} = '{val}'"
            else:
                return f"{field} = '{val}'"
        else:
            # month字段处理
            if time_type == "single":
                return f"{field} = '{val}'"
            elif time_type == "range":
                if "," in val:
                    parts = [p.strip() for p in val.split(",", 1)]
                    if len(parts) == 2:
                        if parts[0] == parts[1]:
                            return f"{field} = '{parts[0]}'"
                        return f"{field} BETWEEN '{parts[0]}' AND '{parts[1]}'"
                return f"{field} = '{val}'"
            elif time_type == "relative":
                if "近" in val and "个月" in val:
                    try:
                        num = int(val.replace("近", "").replace("个月", ""))
                        return f"{field} >= date('now', '-{num} months')"
                    except ValueError:
                        pass
                return f"{field} = '{val}'"
            elif time_type == "list":
                if "," in val:
                    items = [p.strip() for p in val.split(",") if p.strip()]
                    joined = ",".join([f"'{it}'" for it in items])
                    return f"{field} IN ({joined})"
                return f"{field} = '{val}'"
            else:
                return f"{field} = '{val}'"

    def _generate_attribution_sql(self, ir: SemanticQueryIR, default_table: str = "") -> str:
        """生成归因分析SQL"""
        if not default_table:
            s = load_settings()
            default_table = s.dw_table or "dws_user_activity"
        
        attribution = ir.attribution_analysis
        select_parts = ["month"]
        group_by_parts = ["month"]
        
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
        for filter_obj in ir.filters:
            where_conditions.append(self._render_filter(
                filter_obj.field, filter_obj.operator, filter_obj.value,
                filter_obj.time_type, filter_obj.time_unit
            ))
        
        # 添加归因分析的时间范围
        if attribution.base_period and attribution.comparison_period:
            base_months = self._parse_quarter_to_months(attribution.base_period)
            comparison_months = self._parse_quarter_to_months(attribution.comparison_period)
            all_months = base_months + comparison_months
            if all_months:
                month_list = "', '".join(all_months)
                where_conditions.append(f"month IN ('{month_list}')")
        
        # 构建SQL
        select_clause = ", ".join(select_parts)
        where_clause = " AND ".join(where_conditions) if where_conditions else ""
        group_clause = ", ".join(group_by_parts)
        
        sql = f"SELECT {select_clause} FROM {default_table}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if group_clause:
            sql += f" GROUP BY {group_clause}"
        
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
