"""
时间过滤器解析模块

将复杂的时间解析逻辑从pipeline中提取出来，提供更清晰的接口和更好的可维护性。
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime
from datainsight_agent.models.ir import SemanticFilter


class TimeFilterParser:
    """时间过滤器解析器"""
    
    def __init__(self):
        # 预编译正则表达式，提高性能
        self._patterns = {
            'sql_equal': re.compile(rf"(\w+)\s*=\s*['\"](20\d{{2}}-\d{{1,2}})['\"]"),
            'sql_range': re.compile(rf"(\w+)\s*>=\s*['\"](20\d{{2}}-\d{{1,2}})['\"]\s*AND\s*\1\s*<=\s*['\"](20\d{{2}}-\d{{1,2}})['\"]"),
            'single_month': re.compile(r"^(20\d{2}-\d{1,2})$"),
            'comma_range': re.compile(r"^20\d{2}-\d{1,2}$"),
            'question_range': re.compile(r"(20\d{2}-\d{1,2})\s*(?:到|~|–|-|—|\.\.|,|，)\s*(20\d{2}-\d{1,2})"),
            'relative_patterns': [
                re.compile(r"近(\d+)个月"),
                re.compile(r"最近(\d+)个月"),
                re.compile(r"过去(\d+)个月"),
                re.compile(r"last_(\d+)_months?"),
                re.compile(r"recent_(\d+)_months?")
            ],
            'month_list': re.compile(r"20\d{2}-\d{2}"),
            'year': re.compile(r"^(20\d{2})$"),
            'year_month': re.compile(r"(20\d{2})年(\d{1,2})月"),
            'year_only': re.compile(r"(20\d{2})年")
        }
    
    def parse(self, time_filter: str, question: str, time_column: str) -> Optional[SemanticFilter]:
        """
        解析时间过滤器
        
        Args:
            time_filter: 时间过滤器字符串
            question: 问题文本
            time_column: 时间列名
            
        Returns:
            SemanticFilter对象或None
        """
        tf = (time_filter or "").strip()
        q = (question or "").strip()
        
        # 按优先级尝试不同的解析方式
        parsers = [
            self._parse_sql_format,
            self._parse_direct_format,
            self._parse_question_format,
            self._parse_relative_format,
            self._parse_list_format,
            self._parse_year_format
        ]
        
        for parser in parsers:
            result = parser(tf, q, time_column)
            if result:
                return result
        
        return None
    
    def _parse_sql_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """解析SQL格式的时间过滤器"""
        # SQL等值格式：month = '2024-03'
        sql_equal_match = self._patterns['sql_equal'].search(tf)
        if sql_equal_match and sql_equal_match.group(1) == time_column:
            month_value = sql_equal_match.group(2)
            if self._is_valid_month(month_value):
                return SemanticFilter(
                    field=time_column, 
                    operator="=", 
                    value=month_value, 
                    time_type="single", 
                    time_unit="month"
                )
        
        # SQL范围格式：month >= '2024-03' AND month <= '2024-05'
        sql_range_match = self._patterns['sql_range'].search(tf)
        if sql_range_match and sql_range_match.group(1) == time_column:
            start_month = sql_range_match.group(2)
            end_month = sql_range_match.group(3)
            if self._is_valid_month(start_month) and self._is_valid_month(end_month):
                return SemanticFilter(
                    field=time_column, 
                    operator="BETWEEN", 
                    value=f"{start_month},{end_month}", 
                    time_type="range", 
                    time_unit="month"
                )
        
        return None
    
    def _parse_direct_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """解析直接格式的时间过滤器"""
        # 单个月份：2024-03
        single_match = self._patterns['single_month'].match(tf)
        if single_match and self._is_valid_month(single_match.group(1)):
            return SemanticFilter(
                field=time_column, 
                operator="=", 
                value=single_match.group(1), 
                time_type="single", 
                time_unit="month"
            )
        
        # 逗号分隔范围：2024-03,2024-05
        if "," in tf:
            parts = [p.strip() for p in tf.split(",", 1)]
            if len(parts) == 2:
                # 检查格式是否匹配
                if (self._patterns['comma_range'].match(parts[0]) and 
                    self._patterns['comma_range'].match(parts[1])):
                    # 检查月份是否有效
                    if self._is_valid_month(parts[0]) and self._is_valid_month(parts[1]):
                        return SemanticFilter(
                            field=time_column, 
                            operator="BETWEEN", 
                            value=f"{parts[0]},{parts[1]}", 
                            time_type="range", 
                            time_unit="month"
                        )
                    else:
                        # 格式正确但月份无效，抛出异常
                        raise ValueError(f"无效的月份格式: {tf}，请使用 YYYY-MM 格式，如 2024-01")
                else:
                    # 格式不匹配，抛出异常
                    raise ValueError(f"无效的时间格式: {tf}，请使用 YYYY-MM,YYYY-MM 格式，如 2024-01,2024-12")
        
        return None
    
    def _parse_question_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """从问题文本中解析时间格式"""
        # 问题中的范围：2024-03到2024-05
        range_match = self._patterns['question_range'].search(q)
        if range_match:
            return SemanticFilter(
                field=time_column, 
                operator="BETWEEN", 
                value=f"{range_match.group(1)},{range_match.group(2)}", 
                time_type="range", 
                time_unit="month"
            )
        
        # 年月格式：2024年3月
        year_month_match = self._patterns['year_month'].search(q)
        if year_month_match:
            year = year_month_match.group(1)
            month = year_month_match.group(2).zfill(2)
            month_value = f"{year}-{month}"
            if self._is_valid_month(month_value):
                return SemanticFilter(
                    field=time_column, 
                    operator="=", 
                    value=month_value, 
                    time_type="single", 
                    time_unit="month"
                )
        
        return None
    
    def _parse_relative_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """解析相对时间格式"""
        for pattern in self._patterns['relative_patterns']:
            match = pattern.search(q.lower())
            if match:
                return SemanticFilter(
                    field=time_column, 
                    operator="BETWEEN", 
                    value=str(int(match.group(1))), 
                    time_type="relative", 
                    time_unit="month"
                )
        return None
    
    def _parse_list_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """解析月份列表格式"""
        months = self._patterns['month_list'].findall(tf)
        if len(months) > 1:
            valid_months = [m for m in months if self._is_valid_month(m)]
            if len(valid_months) > 1:
                return SemanticFilter(
                    field=time_column, 
                    operator="IN", 
                    value=",".join(valid_months), 
                    time_type="list", 
                    time_unit="month"
                )
        return None
    
    def _parse_year_format(self, tf: str, q: str, time_column: str) -> Optional[SemanticFilter]:
        """解析年份格式"""
        # 直接年份：2024
        year_match = self._patterns['year'].match(tf)
        if year_match:
            year = year_match.group(1)
            return SemanticFilter(
                field=time_column, 
                operator="BETWEEN", 
                value=f"{year}-01,{year}-12", 
                time_type="range", 
                time_unit="month"
            )
        
        # 问题中的年份：2024年
        year_only_match = self._patterns['year_only'].search(q)
        if year_only_match:
            year = year_only_match.group(1)
            return SemanticFilter(
                field=time_column, 
                operator="BETWEEN", 
                value=f"{year}-01,{year}-12", 
                time_type="range", 
                time_unit="month"
            )
        
        return None
    
    def _is_valid_month(self, month_str: str) -> bool:
        """验证月份字符串是否有效"""
        try:
            # 支持一位数和两位数的月份格式
            month_part = month_str.split('-')[1]
            month = int(month_part)
            return 1 <= month <= 12
        except (ValueError, IndexError):
            return False
    
    # ===== 动态时间工具方法（供外部复用，避免重复造轮子） =====
    @staticmethod
    def get_current_month() -> str:
        """获取当前月份，格式：YYYY-MM"""
        now = datetime.now()
        return now.strftime("%Y-%m")

    @staticmethod
    def get_last_month() -> str:
        """获取上个月份，格式：YYYY-MM"""
        now = datetime.now()
        if now.month == 1:
            year = now.year - 1
            month = 12
        else:
            year = now.year
            month = now.month - 1
        return f"{year}-{month:02d}"

    @staticmethod
    def get_year_range(year: int) -> str:
        """获取某年的范围，格式：YYYY-01,YYYY-12"""
        return f"{int(year)}-01,{int(year)}-12"

    @staticmethod
    def get_relative_time_mapping() -> dict:
        """获取相对时间的动态映射"""
        current_month = TimeFilterParser.get_current_month()
        last_month = TimeFilterParser.get_last_month()
        y = datetime.now().year
        return {
            "本月": current_month,
            "上月": last_month,
            "今年": f"{y}-01,{y}-12",
            "去年": f"{y-1}-01,{y-1}-12",
        }

    def create_default_filter(self, time_column: str, year: str = None) -> SemanticFilter:
        """创建默认时间过滤器"""
        # 使用当前年份作为默认值
        if year is None:
            year = str(datetime.now().year)
        
        return SemanticFilter(
            field=time_column, 
            operator="BETWEEN", 
            value=f"{year}-01,{year}-12", 
            time_type="range", 
            time_unit="month"
        )


# 全局实例，避免重复创建
_parser_instance = None

def parse_time_filter(time_filter: str, question: str, time_column: str) -> Optional[SemanticFilter]:
    """
    解析时间过滤器的便捷函数
    
    Args:
        time_filter: 时间过滤器字符串
        question: 问题文本
        time_column: 时间列名
        
    Returns:
        SemanticFilter对象或None
    """
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = TimeFilterParser()
    return _parser_instance.parse(time_filter, question, time_column)


