"""
测试评估配置文件
用于存储测试评估中的各种硬编码值和配置参数
"""

# 核心指标列表
CORE_METRICS = ['mau', 'dau', 'uv', 'pv', 'gmv', 'aov']

# 指标关键词映射
METRIC_KEYWORDS = {
    # 核心指标
    'core': ['mau', 'dau', 'uv', 'pv', 'gmv', 'aov'],
    # 中文全称
    'chinese_full': ['月活跃用户', '日活跃用户', '独立访客', '页面访问', '成交总额', '客单价'],
    # 中文简称
    'chinese_short': ['月活', '日活', '访客', '浏览量', '访问量'],
    # 业务同义词
    'business_synonyms': [
        '活跃用户', '用户活跃度', '活跃度统计', '用户数', '访问次数', '页面浏览量',
        '独立用户', '独立用户数', '唯一访客', '唯一用户'
    ]
}

# 时间关键词
TIME_KEYWORDS = [
    # 中文时间词
    '年', '月', '日', '季度', '周', '小时', '时段',
    # 英文时间词
    'year', 'month', 'day', 'quarter', 'week', 'hour',
    # 相对时间词
    '最近', '今年', '去年', '本月', '上月', '本周', '上周',
    # 具体年份
    '2025', '2024', '2023',
    # 季度标识
    'q1', 'q2', 'q3', 'q4'
]

# 查询相关词汇
QUERY_KEYWORDS = [
    '查询', '统计', '分析', '对比', '趋势', '分布', '排名',
    'query', 'statistics', 'analysis', 'compare', 'trend', 'distribution', 'ranking'
]

# 权重配置
WEIGHT_CONFIG = {
    # 相关性计算权重
    'relevance': {
        'vector_similarity': 0.6,
        'keyword_match': 0.4
    },
    # 指标匹配权重
    'metric_matching': {
        'core_metrics': 0.8,
        'chinese_full': 0.6,
        'default': 1.0
    }
}

# 质量阈值配置
QUALITY_THRESHOLDS = {
    'high_quality_score': 0.7,
    'relevance_threshold': 0.5
}

# 模拟数据配置
MOCK_DATA_CONFIG = {
    'default_score': 0.9,
    'entity_id_prefix': 'mock_'
}

# 期望的实体类型
EXPECTED_ENTITY_TYPES = ['metric', 'dimension', 'mapping']
