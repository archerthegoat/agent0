from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from datainsight_agent.models.ir import SemanticQueryIR, SemanticFilter, SemanticAggregation
from datainsight_agent.config.settings import load_settings


class IRValidationResult(BaseModel):
    """IR验证结果"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []


class IRValidator:
    """增强的IR验证器，提供全面的IR语义和结构验证"""
    
    def __init__(self):
        self.settings = load_settings()
        # 预加载允许的列名（如果配置了的话）
        self._allowed_columns = set()
        if self.settings.dw_allowed_columns_csv:
            self._allowed_columns = set(
                col.strip() for col in self.settings.dw_allowed_columns_csv.split(",")
            )
    
    def validate(self, ir: SemanticQueryIR) -> IRValidationResult:
        """全面验证IR对象"""
        errors = []
        warnings = []
        suggestions = []
        
        # 1. 基础结构验证
        self._validate_basic_structure(ir, errors, warnings)
        
        # 2. 聚合验证
        self._validate_aggregations(ir, errors, warnings, suggestions)
        
        # 3. 过滤器验证
        self._validate_filters(ir, errors, warnings, suggestions)
        
        # 4. 分组验证
        self._validate_group_by(ir, errors, warnings, suggestions)
        
        # 5. 时间过滤验证
        self._validate_time_filters(ir, errors, warnings, suggestions)
        
        # 6. 业务逻辑验证
        self._validate_business_logic(ir, errors, warnings, suggestions)
        
        return IRValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _validate_basic_structure(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str]):
        """验证基础结构"""
        # 检查是否有聚合或指标
        if not ir.aggregations and not ir.target_metrics:
            errors.append("IR必须包含至少一个聚合函数或目标指标")
        
        # 检查空的group_by字段
        if ir.group_by:
            empty_groups = [g for g in ir.group_by if not g or not g.strip()]
            if empty_groups:
                warnings.append(f"发现{len(empty_groups)}个空的分组字段")
                # 清理空字段
                ir.group_by = [g for g in ir.group_by if g and g.strip()]
    
    def _validate_aggregations(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证聚合函数"""
        valid_functions = {"COUNT", "SUM", "AVG", "MAX", "MIN", "COUNT_DISTINCT"}
        
        for agg in ir.aggregations:
            # 验证聚合函数名
            if agg.function.upper() not in valid_functions:
                errors.append(f"不支持的聚合函数: {agg.function}")
                suggestions.append(f"支持的聚合函数: {', '.join(valid_functions)}")
            
            # COUNT不需要字段，其他聚合需要
            if agg.function.upper() in {"SUM", "AVG", "MAX", "MIN"} and not agg.field:
                errors.append(f"{agg.function}聚合函数必须指定字段")
            
            # 检查字段名是否在允许列表中
            if agg.field and self._allowed_columns and agg.field not in self._allowed_columns:
                warnings.append(f"聚合字段 '{agg.field}' 不在允许的列表中")
            
            # 检查别名冲突
            if agg.alias:
                alias_conflicts = [other for other in ir.aggregations 
                                 if other != agg and other.alias == agg.alias]
                if alias_conflicts:
                    errors.append(f"聚合别名冲突: '{agg.alias}'")
    
    def _validate_filters(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证过滤器"""
        valid_operators = {"=", "!=", "<>", ">", ">=", "<", "<=", "IN", "NOT IN", "LIKE", "NOT LIKE", "BETWEEN", "IS NULL", "IS NOT NULL"}
        
        for filter_obj in ir.filters:
            # 验证操作符
            if filter_obj.operator.upper() not in valid_operators:
                errors.append(f"不支持的过滤操作符: {filter_obj.operator}")
                suggestions.append(f"支持的操作符: {', '.join(valid_operators)}")
            
            # 验证字段名
            if self._allowed_columns and filter_obj.field not in self._allowed_columns:
                warnings.append(f"过滤字段 '{filter_obj.field}' 不在允许的列表中")
            
            # 验证值的格式
            self._validate_filter_value(filter_obj, errors, warnings, suggestions)
    
    def _validate_filter_value(self, filter_obj: SemanticFilter, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证过滤器值的格式"""
        op = filter_obj.operator.upper()
        value = filter_obj.value
        
        # BETWEEN需要两个值
        if op == "BETWEEN":
            if "," not in value:
                errors.append(f"BETWEEN操作符需要两个值，用逗号分隔: {value}")
            else:
                parts = value.split(",")
                if len(parts) != 2:
                    errors.append(f"BETWEEN操作符只能有两个值: {value}")
        
        # IN需要多个值
        if op in {"IN", "NOT IN"}:
            if "," not in value and not value.startswith("("):
                warnings.append(f"IN操作符通常需要多个值: {value}")
        
        # NULL检查
        if op in {"IS NULL", "IS NOT NULL"} and value:
            warnings.append(f"{op}操作符不需要值，但提供了: {value}")
    
    def _validate_group_by(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证分组字段"""
        if not ir.group_by:
            return
        
        # 检查分组字段是否在允许列表中
        for group_field in ir.group_by:
            if self._allowed_columns and group_field not in self._allowed_columns:
                warnings.append(f"分组字段 '{group_field}' 不在允许的列表中")
        
        # 检查重复的分组字段
        unique_groups = set()
        duplicates = []
        for group_field in ir.group_by:
            if group_field in unique_groups:
                duplicates.append(group_field)
            unique_groups.add(group_field)
        
        if duplicates:
            warnings.append(f"发现重复的分组字段: {', '.join(duplicates)}")
            # 去重
            ir.group_by = list(unique_groups)
    
    def _validate_time_filters(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证时间过滤器"""
        time_filters = [f for f in ir.filters if getattr(f, 'time_type', None)]
        
        if len(time_filters) > 1:
            warnings.append(f"发现多个时间过滤器({len(time_filters)}个)，可能导致冲突")
        
        for time_filter in time_filters:
            self._validate_single_time_filter(time_filter, errors, warnings, suggestions)
    
    def _validate_single_time_filter(self, time_filter: SemanticFilter, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证单个时间过滤器"""
        time_type = getattr(time_filter, 'time_type', None)
        time_unit = getattr(time_filter, 'time_unit', None)
        
        if not time_type:
            warnings.append("时间过滤器缺少time_type字段")
        
        if not time_unit:
            warnings.append("时间过滤器缺少time_unit字段")
        
        # 验证时间类型和操作符的匹配
        if time_type == "single" and time_filter.operator.upper() != "=":
            warnings.append(f"单个时间过滤器应使用'='操作符，当前: {time_filter.operator}")
        
        if time_type == "range" and time_filter.operator.upper() != "BETWEEN":
            warnings.append(f"时间范围过滤器应使用'BETWEEN'操作符，当前: {time_filter.operator}")
        
        if time_type == "list" and time_filter.operator.upper() not in {"IN", "NOT IN"}:
            warnings.append(f"时间列表过滤器应使用'IN'操作符，当前: {time_filter.operator}")
        
        # 验证时间值格式
        self._validate_time_value_format(time_filter, errors, warnings, suggestions)
    
    def _validate_time_value_format(self, time_filter: SemanticFilter, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证时间值格式"""
        import re
        
        time_unit = getattr(time_filter, 'time_unit', 'month')
        value = time_filter.value
        
        if time_unit == "month":
            # 验证月份格式 YYYY-MM 或 YYYY-M
            month_pattern = r"^\d{4}-\d{1,2}$"
            if time_filter.operator.upper() == "BETWEEN":
                # 范围格式 YYYY-MM,YYYY-MM
                if "," in value:
                    parts = value.split(",")
                    if len(parts) == 2:
                        for part in parts:
                            if not re.match(month_pattern, part.strip()):
                                errors.append(f"无效的月份格式: {part.strip()}")
                    else:
                        errors.append(f"BETWEEN时间范围格式错误: {value}")
                else:
                    errors.append(f"BETWEEN操作符需要两个月份值: {value}")
            elif time_filter.operator.upper() == "=":
                if not re.match(month_pattern, value):
                    errors.append(f"无效的月份格式: {value}")
        
        elif time_unit == "year":
            # 验证年份格式 YYYY
            year_pattern = r"^\d{4}$"
            if not re.match(year_pattern, value):
                errors.append(f"无效的年份格式: {value}")
    
    def _validate_business_logic(self, ir: SemanticQueryIR, errors: List[str], warnings: List[str], suggestions: List[str]):
        """验证业务逻辑"""
        # 检查是否有分组但没有聚合
        if ir.group_by and not ir.aggregations:
            warnings.append("使用了分组但没有聚合函数，可能需要添加聚合")
        
        # 检查是否有聚合但没有分组（对于某些业务场景可能是警告）
        if ir.aggregations and not ir.group_by:
            suggestions.append("考虑添加分组维度以获得更详细的分析结果")
        
        # 检查时间过滤的必要性
        time_filters = [f for f in ir.filters if getattr(f, 'time_type', None)]
        if not time_filters and self.settings.time_require_explicit:
            warnings.append("缺少明确的时间过滤条件")
        
        # 检查指标和聚合的一致性
        if ir.target_metrics and ir.aggregations:
            # 确保指标和聚合不冲突
            for metric in ir.target_metrics:
                conflicting_aggs = [agg for agg in ir.aggregations 
                                  if agg.alias and agg.alias.lower() == metric.lower()]
                if conflicting_aggs:
                    warnings.append(f"目标指标'{metric}'与聚合别名冲突")


def validate_ir(ir: SemanticQueryIR) -> IRValidationResult:
    """便捷函数，验证IR对象"""
    validator = IRValidator()
    return validator.validate(ir)
