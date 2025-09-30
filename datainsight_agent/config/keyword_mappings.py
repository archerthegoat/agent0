"""
关键词映射配置

将硬编码的关键词映射提取到配置文件中，便于维护和扩展。
"""

from typing import Dict, List

# 维度关键词映射
DIMENSION_KEYWORDS: Dict[str, str] = {
    "性别": "user_gender",
    "年龄": "user_age_group", 
    "产品类别": "product_category",
    "支付方式": "payment_method",
    "订单状态": "order_status",
    "配送方式": "delivery_method",
    "营销来源": "marketing_source",
    "vip等级": "user_vip_level",
    "时段": "time_period",
    "设备": "device",
    "渠道": "channel_code",
    "地区": "region",
    "用户等级": "user_level"
}

# 度量关键词映射
METRIC_KEYWORDS: Dict[str, str] = {
    # MAU相关
    "活跃度": "mau",
    "活跃用户": "mau", 
    "月活": "mau",
    "月活跃用户": "mau",
    "月活跃用户数": "mau",
    "活跃用户数": "mau",
    
    # DAU相关  
    "日活": "dau",
    "日活跃用户": "dau",
    "日活跃用户数": "dau",
    
    # UV相关
    "独立访客": "uv",
    "独立用户": "uv",
    "独立用户数": "uv",
    
    # PV相关
    "浏览量": "pv",
    "访问量": "pv",
    
    # GMV相关
    "成交总额": "gmv",
    "交易总额": "gmv",
    
    # AOV相关
    "客单价": "aov",
    "平均订单": "aov",
    "订单价值": "aov",
    
    # 其他
    "收入": "revenue",
    "营收": "revenue",
    "订单数": "orders",
    "转化率": "conversion_rate",
    "留存率": "retention_rate",
    "跳出率": "bounce_rate",
    "新用户": "new_users",
    "流失用户": "churn_users",
    
    # 缩写直接识别（问题文本会lowercase）
    "mau": "mau",
    "uv": "uv",
    "pv": "pv",
    "dau": "dau",
    "gmv": "gmv",
    "aov": "aov"
}

# Q2Q智能跳过机制的关键词
Q2Q_METRIC_KEYWORDS: List[str] = [
    "mau", "uv", "pv", "dau", "月活", "日活", "独立访客", "浏览量", "访问量"
]

# 动态生成年份关键词
from datetime import datetime
_current_year = str(datetime.now().year)
_next_year = str(datetime.now().year + 1)

Q2Q_TIME_KEYWORDS: List[str] = [
    _current_year, _next_year, "月", "年", "季度", "周", "日", "最近", "近"
]

Q2Q_GROUP_KEYWORDS: List[str] = [
    "渠道", "地区", "城市", "省份", "国家", "平台", "设备", "来源"
]

Q2Q_FUZZY_KEYWORDS: List[str] = [
    "对比", "分析", "趋势", "变化", "增长", "下降", "比较", "差异"
]

# KB上下文判断的关键词
KB_KEYWORDS: List[str] = [
    "对比", "分析", "趋势", "变化", "增长", "下降", "比较", "差异",
    "渠道", "地区", "城市", "省份", "国家", "平台", "设备", "来源",
    "用户", "活跃", "留存", "转化", "漏斗", "归因", "细分"
]

# 聚合函数映射
AGGREGATION_MAPPING: Dict[str, Dict[str, str]] = {
    "mau": {"function": "COUNT", "field": "DISTINCT user_id"},
    "uv": {"function": "COUNT", "field": "DISTINCT user_id"},
    "new_users": {"function": "COUNT", "field": "DISTINCT user_id"},
    "churn_users": {"function": "COUNT", "field": "DISTINCT user_id"},
    "orders": {"function": "COUNT", "field": "DISTINCT user_id"},
    "pv": {"function": "COUNT", "field": "page_view_id"},
    "gmv": {"function": "SUM", "field": "order_amount"},
    "revenue": {"function": "SUM", "field": "order_amount"},
    "aov": {"function": "AVG", "field": "order_amount"},
    "conversion_rate": {"function": "AVG", "field": "conversion_rate_flag"},
    "retention_rate": {"function": "AVG", "field": "retention_rate_flag"},
    "bounce_rate": {"function": "AVG", "field": "bounce_rate_flag"}
}

# （已废弃）默认聚合与过滤常量不再使用，聚合/过滤由注册表提供
