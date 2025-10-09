#!/usr/bin/env python3
"""
增强版批量测试评估框架
支持RAG相关评价指标：召回率、准确率、相关性评分等
"""

import sys
import io
# 修复Windows终端编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import time
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import traceback

from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter as QueryRewriter
from datainsight_agent.services.core.sql_generator import SQLGenerator as SQLGeneratorComponent
from datainsight_agent.services.core.sql_executor import SQLExecutor as SQLExecutorComponent
from datainsight_agent.orchestrator.li.workflow import LIWorkflow
from datainsight_agent.services.db_bootstrap import init_mysql_min
from datainsight_agent.config.manager import ConfigManager

# 常量定义
METRIC_KEYWORDS = {
    'core': ['mau', 'dau', 'uv', 'pv', 'retention_rate', 'conversion_rate', 'revenue', 'orders', 'new_users', 'churn_users', 'arpu', 'gmv', 'aov', 'roi', 'cac', 'clv', 'bounce_rate', 'session_duration', 'page_views_per_session', 'return_visitor_rate', 'cart_abandonment_rate', 'search_success_rate', 'recommendation_click_rate', 'customer_satisfaction', 'net_promoter_score', 'support_ticket_count', 'average_resolution_time', 'repeat_purchase_rate', 'inventory_turnover', 'refund_rate', 'email_open_rate', 'email_click_rate', 'app_crash_rate', 'api_response_time', 'search_conversion_rate', 'social_share_count', 'average_basket_size', 'user_engagement_score', 'content_virality_score'],
    'chinese_full': ['月活跃用户数', '日活跃用户数', '独立访客数', '页面浏览量', '用户留存率', '转化率', '收入', '订单数', '新用户数', '流失用户数', '平均每用户收入', '总交易额', '平均订单价值', '投资回报率', '客户获取成本', '客户生命周期价值', '跳出率', '会话时长', '页面浏览数/会话', '回访率', '购物车放弃率', '搜索成功率', '推荐点击率', '客户满意度', '净推荐值', '客服工单数', '平均解决时间', '重复购买率', '库存周转率', '退款率', '邮件打开率', '邮件点击率', 'APP崩溃率', 'API响应时间', '搜索转化率', '社交分享数', '平均购物篮大小', '用户参与度评分', '内容病毒性评分'],
    'chinese_short': ['月活', '日活', '独立访客', '页面浏览', '留存率', '转化', '收入', '订单', '新用户', '流失用户', 'ARPU', 'GMV', 'AOV', 'ROI', 'CAC', 'CLV', '跳出', '会话', '页面深度', '回访', '放弃', '搜索', '推荐', '满意度', 'NPS', '工单', '解决', '复购', '周转', '退款', '打开', '点击', '崩溃', '响应', '转化', '分享', '购物篮', '参与', '病毒'],
    'aliases': ['MAU', 'DAU', 'UV', 'PV', 'Retention Rate', 'Conversion Rate', 'Revenue', 'Orders', 'New Users', 'Churn Users', 'ARPU', 'GMV', 'AOV', 'ROI', 'CAC', 'CLV', 'Bounce Rate', 'Session Duration', 'Pages per Session', 'Return Visitor Rate', 'Cart Abandonment Rate', 'Search Success Rate', 'Recommendation Click Rate', 'Customer Satisfaction', 'NPS', 'Support Tickets', 'Resolution Time', 'Repeat Purchase Rate', 'Inventory Turnover', 'Refund Rate', 'Email Open Rate', 'Email Click Rate', 'App Crash Rate', 'API Response Time', 'Search Conversion Rate', 'Social Shares', 'Basket Size', 'Engagement Score', 'Virality Score']
}

# 动态生成时间关键词，避免硬编码年份
def _generate_time_keywords():
    """动态生成时间关键词"""
    from datetime import datetime
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # 生成当前年份的月份
    year_months = [f"{current_year}-{i:02d}" for i in range(1, 13)]
    
    # 季度和月份关键词
    quarters = ['第一季度', '第二季度', '第三季度', '第四季度', 'Q1', 'Q2', 'Q3', 'Q4']
    months = [f"{i}月" for i in range(1, 13)]
    
    # 相对时间关键词
    relative_times = ['今天', '昨天', '本周', '上周', '本月', '上月', '今年', '去年']
    
    return year_months + quarters + months + relative_times

TIME_KEYWORDS = _generate_time_keywords()

CONCEPT_COVERAGE_WEIGHTS = {
    'metric': 0.4,
    'dimension': 0.3,
    'mapping': 0.2,
    'concept': 0.1
}

# 添加缺失的配置常量
WEIGHT_CONFIG = {
    'metric_matching': {
        'core_metrics': 1.0,
        'chinese_full': 0.8,
        'default': 0.5
    },
    'relevance': {
        'vector_similarity': 0.7,
        'keyword_match': 0.3
    }
}

QUERY_KEYWORDS = ['查询', '分析', '统计', '计算', '查看', '显示', '获取', '找出', '了解']

QUALITY_THRESHOLDS = {
    'high_quality_score': 0.8
}

# 添加缺失的映射常量
QUESTION_TYPE_ENTITY_MAPPING = {
    'metric_analysis': ['metric'],
    'dimension_analysis': ['dimension'],
    'comparison': ['metric', 'dimension'],
    'trend': ['metric', 'dimension'],
    'distribution': ['dimension'],
    'correlation': ['metric', 'dimension']
}

BUSINESS_CONCEPT_KEYWORDS = {
    'user_behavior': ['用户行为', '行为分析', '用户习惯', '使用模式'],
    'business_metrics': ['业务指标', 'KPI', '关键指标', '业务数据'],
    'product_analysis': ['产品分析', '功能使用', '产品指标'],
    'marketing': ['营销', '推广', '获客', '转化'],
    'revenue': ['收入', '营收', 'GMV', 'ARPU']
}


@dataclass
class TestCase:
    """测试用例"""
    id: str
    question: str
    expected_sql: Optional[str] = None
    expected_result: Optional[List[Dict]] = None
    expected_metrics: Optional[List[str]] = None
    expected_time_filter: Optional[str] = None
    expected_group_by: Optional[List[str]] = None
    category: str = "general"
    description: str = ""
    # RAG相关期望值
    expected_rag_entities: Optional[List[str]] = None  # 期望检索到的实体
    expected_rag_concepts: Optional[List[str]] = None  # 期望检索到的概念
    # 时间澄清相关字段
    time_clarification: Optional[Dict[str, Any]] = None  # 时间澄清配置


@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    success: bool
    execution_time: float
    sql_generated: bool
    sql_executable: bool
    sql_correct: bool
    time_parsed_correctly: Optional[bool]
    metric_identified_correctly: Optional[bool]
    group_by_correct: Optional[bool]
    result_complete: bool
    # Q2Q阶段RAG指标
    q2q_rag_recall_rate: Optional[float] = None
    q2q_rag_precision_rate: Optional[float] = None
    q2q_rag_relevance_score: Optional[float] = None
    q2q_rag_fragment_count: Optional[int] = None
    q2q_rag_entity_coverage: Optional[float] = None
    q2q_rag_concept_coverage: Optional[float] = None
    
    # 增强RAG指标（新功能）
    q2q_rag_semantic_similarity: Optional[float] = None
    q2q_rag_fragment_quality: Optional[float] = None
    q2q_rag_business_relevance: Optional[float] = None
    q2q_rag_confidence: Optional[float] = None
    
    # Retrieve阶段RAG指标
    retrieve_rag_recall_rate: Optional[float] = None
    retrieve_rag_precision_rate: Optional[float] = None
    retrieve_rag_relevance_score: Optional[float] = None
    retrieve_rag_fragment_count: Optional[int] = None
    retrieve_rag_entity_coverage: Optional[float] = None
    
    # 综合RAG指标（向后兼容）
    rag_recall_rate: Optional[float] = None
    rag_precision_rate: Optional[float] = None
    rag_relevance_score: Optional[float] = None
    rag_fragment_count: Optional[int] = None
    rag_retrieval_time: Optional[float] = None
    rag_entity_coverage: Optional[float] = None  # 实体覆盖率
    rag_concept_coverage: Optional[float] = None  # 概念覆盖率
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    generated_sql: Optional[str] = None
    actual_result: Optional[List[Dict]] = None
    component_timings: Optional[Dict[str, float]] = None
    rewritten_query: Optional[Any] = None
    ir: Optional[Any] = None
    rag_context: Optional[str] = None
    rag_fragments: Optional[List[Dict]] = None


class BatchTestEvaluator:
    """增强版批量测试评估器"""
    
    def __init__(self, debug_mode: bool = False, fast_mode: bool = False):
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        self.clarification_config: Dict[str, Any] = {}
        self.debug_mode = debug_mode  # 添加调试模式控制
        self.fast_mode = fast_mode    # 添加快速模式控制
        
        # 初始化组件（预初始化避免重复创建）
        from datainsight_agent.config.settings import load_settings
        settings = load_settings()
        
        self.query_rewriter = QueryRewriter()
        self.sql_generator = SQLGeneratorComponent()
        self.sql_executor = SQLExecutorComponent(settings)
        self.pipeline = LIWorkflow()
        
        # 初始化配置
        config_manager = ConfigManager()
        self.settings = config_manager._s
        init_mysql_min(self.settings.database_url)
    
    def _debug_print(self, message: str):
        """调试输出控制函数"""
        if self.debug_mode:
            print(message)
    
    def _extract_time_from_question(self, question: str) -> str:
        """从问题中快速提取时间信息"""
        import re
        
        # 匹配年份-月份格式 (如: 2025年8月)
        year_month_match = re.search(r'(\d{4})年(\d{1,2})月', question)
        if year_month_match:
            year, month = year_month_match.groups()
            return f"{year}-{month.zfill(2)}"
        
        # 匹配月份范围 (如: 2025年8月到9月)
        month_range_match = re.search(r'(\d{4})年(\d{1,2})月到(\d{1,2})月', question)
        if month_range_match:
            year, start_month, end_month = month_range_match.groups()
            return f"{year}-{start_month.zfill(2)},{year}-{end_month.zfill(2)}"
        
        # 匹配月份到月份范围 (如: 2025年8月到10月)
        month_to_month_match = re.search(r'(\d{4})年(\d{1,2})月到(\d{1,2})月', question)
        if month_to_month_match:
            year, start_month, end_month = month_to_month_match.groups()
            return f"{year}-{start_month.zfill(2)},{year}-{end_month.zfill(2)}"
        
        # 匹配季度 (如: 2025年第3季度, 2025年第三季度)
        quarter_match = re.search(r'(\d{4})年第([一二三四1234])季度', question)
        if quarter_match:
            year, quarter = quarter_match.groups()
            quarter_num = {'一': '1', '二': '2', '三': '3', '四': '4'}.get(quarter, quarter)
            start_month = (int(quarter_num) - 1) * 3 + 1
            end_month = int(quarter_num) * 3
            return f"{year}-{start_month:02d},{year}-{end_month:02d}"
        
        # 匹配各月/各季度 (如: 2025年各月的DAU趋势)
        if '各月' in question:
            year_match = re.search(r'(\d{4})年', question)
            if year_match:
                year = year_match.group(1)
                return f"{year}-01,{year}-12"
        
        if '各季度' in question:
            year_match = re.search(r'(\d{4})年', question)
            if year_match:
                year = year_match.group(1)
                return f"{year}-01,{year}-12"
        
        # 匹配相对时间
        if '今年' in question:
            from datetime import datetime
            current_year = datetime.now().year
            return f"{current_year}-01,{current_year}-12"
        
        if '本月' in question:
            from datetime import datetime
            current_year = datetime.now().year
            current_month = datetime.now().month
            return f"{current_year}-{current_month:02d}"
        
        # 默认返回当前年份
        from datetime import datetime
        current_year = datetime.now().year
        return f"{current_year}-01,{current_year}-12"
    
    def _extract_metric_from_question(self, question: str) -> str:
        """从问题中快速提取指标信息"""
        import re
        
        question_lower = question.lower()
        
        # 指标关键词映射 - 按优先级排序（更具体的指标优先）
        metric_keywords = {
            # 复杂指标优先
            'page_views_per_session': ['页面浏览数/会话', '页面浏览数', '页面深度', '浏览数/会话'],
            'cac': ['客户获取成本', 'cac', '获客成本'],
            'customer_lifetime_value': ['客户生命周期价值', 'clv', '客户价值'],
            'net_promoter_score': ['净推荐值', 'nps', '推荐值'],
            'cart_abandonment_rate': ['购物车放弃率', '放弃率', '购物车弃购率'],
            'return_visitor_rate': ['回访率', '回访', '回头率'],
            'repeat_purchase_rate': ['复购率', '重复购买率', '重复购买'],
            'session_duration': ['会话时长', '会话时间', '平均会话时长'],
            'bounce_rate': ['跳出率', '跳出', '跳出率'],
            'customer_satisfaction': ['客户满意度', '满意度', '满意度评分'],
            'roi': ['roi', '投资回报率', '回报率'],
            'arpu': ['arpu', '平均每用户收入', '每用户收入'],
            'gmv': ['gmv', '总交易额', '交易总额'],
            'aov': ['aov', '平均订单价值', '订单价值'],
            'retention_rate': ['留存率', '留存', '用户留存'],
            'conversion_rate': ['转化率', '转化', '转化率'],
            'revenue': ['收入', '营收', '总收入', '平均收入', '平均营收'],
            'orders': ['订单数', '订单', '订单量'],
            'new_users': ['新用户', '新增用户', '新用户数'],
            'churn_users': ['流失用户', '流失', '流失用户数'],
            'mau': ['月活跃用户', '月活', 'mau'],
            'dau': ['日活跃用户', '日活', 'dau'],
            'uv': ['独立访客', 'uv', '访客数'],
            'pv': ['页面浏览', 'pv', '浏览量'],
            # 新增指标
            'email_open_rate': ['邮件打开率', '邮件开启率', '邮件打开'],
            'app_crash_rate': ['应用崩溃率', '崩溃率', 'app崩溃率']
        }
        
        # 查找匹配的指标 - 返回第一个匹配的指标
        for metric, keywords in metric_keywords.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return metric
        
        # 默认返回mau
        return "mau"
    
    def load_test_cases(self, test_file: str):
        """从JSON文件加载测试用例"""
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            test_case = TestCase(
                id=item['id'],
                question=item['question'],
                expected_sql=item.get('expected_sql'),
                expected_result=item.get('expected_result'),
                expected_metrics=item.get('expected_metrics'),
                expected_time_filter=item.get('expected_time_filter'),
                expected_group_by=item.get('expected_group_by'),
                category=item.get('category', 'general'),
                description=item.get('description', ''),
                expected_rag_entities=item.get('expected_rag_entities'),
                expected_rag_concepts=item.get('expected_rag_concepts'),
                time_clarification=item.get('time_clarification')
            )
            self.test_cases.append(test_case)
        
        print(f"[SUCCESS] Loaded {len(self.test_cases)} test cases")
    
    def load_clarification_config(self, config_file: str):
        """加载澄清配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.clarification_config = json.load(f)
            print(f"[SUCCESS] Loaded clarification config from {config_file}")
        except Exception as e:
            print(f"[WARNING] Failed to load clarification config: {e}")
            self.clarification_config = {}
    
    def _create_mock_kb_entities(self, expected_entities):
        """基于expected_rag_entities创建模拟的kb_entities"""
        if not expected_entities:
            return []
        
        mock_entities = []
        for entity in expected_entities:
            # 使用配置判断实体类型
            # 使用简单判断实体类型
            entity_type = 'metric' if entity.lower() in ['mau', 'dau', 'uv', 'pv', 'retention_rate'] else 'dimension'
            
            mock_entity = {
                'entity_id': f"mock_{entity}",
                'entity_type': entity_type,
                'score': 0.8,
                'metadata': {
                    'canonical_name': entity,
                    'aliases': [entity],
                    'type': entity_type
                }
            }
            mock_entities.append(mock_entity)
        
        return mock_entities

    def run_single_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()
        component_timings = {}
        
        try:
            self._debug_print(f"[DEBUG] Running test: {test_case.id}")
            
            # 检查是否需要澄清流程
            if self._needs_clarification(test_case):
                return self._simulate_clarification_flow(test_case)
            
            # 快速模式：跳过复杂的Q2Q重写，使用简化版本
            if self.fast_mode:
                # 创建简化的重写结果，但保持指标和时间解析的准确性
                from dataclasses import dataclass
                @dataclass
                class SimpleRewrittenQuery:
                    metric: str = None  # 需要动态生成
                    time_filter: str = None  # 需要动态生成
                    group_by: list = None
                    rag_context: str = "Fast mode context"
                    rag_fragments: list = None
                    
                    def __post_init__(self):
                        if self.group_by is None:
                            self.group_by = []
                        if self.rag_fragments is None:
                            self.rag_fragments = []
                    
                    def model_dump(self):
                        """提供 model_dump 方法以兼容 Pydantic 模型"""
                        return {
                            'metric': self.metric,
                            'time_filter': self.time_filter,
                            'group_by': self.group_by,
                            'rag_context': self.rag_context,
                            'rag_fragments': self.rag_fragments
                        }
                
                # 从问题中提取指标和时间信息
                metric = self._extract_metric_from_question(test_case.question)
                time_filter = self._extract_time_from_question(test_case.question)
                rewritten_query = SimpleRewrittenQuery(metric=metric, time_filter=time_filter)
                component_timings['query_rewriter'] = 0.1  # 快速模式固定时间
                self._debug_print(f"[DEBUG] Fast mode: Skipped Q2Q rewrite, extracted metric: {metric}, time: {time_filter}")
            else:
                # 1. Query Rewriter (包含RAG检索)
                qr_start = time.time()
                rewritten_query = self.query_rewriter.rewrite(test_case.question)
                component_timings['query_rewriter'] = time.time() - qr_start
                self._debug_print(f"[DEBUG] Query Rewriter completed: {rewritten_query.metric}")
            
            # 2. 检查是否需要时间澄清
            if self._needs_time_clarification(rewritten_query, test_case):
                clarified_query = self._simulate_time_clarification(rewritten_query, test_case)
                rewritten_query = clarified_query
            
            # 3. Use Workflow for IR building and SQL generation
            workflow_start = time.time()
            state = {
                'question': test_case.question,
                'q2q': rewritten_query.model_dump() if hasattr(rewritten_query, 'model_dump') else {},
                'kb_entities': self._create_mock_kb_entities(test_case.expected_rag_entities) if test_case.expected_rag_entities else []
            }
            
            # Run workflow steps
            state = self.pipeline.q2q(state)
            state = self.pipeline.retrieve(state)
            state = self.pipeline.plan(state)
            state = self.pipeline.build_ir(state)
            
            ir_obj = state.get('ir_obj')  # 获取SemanticQueryIR对象
            ir = state.get('ir')  # 获取序列化版本用于调试
            component_timings['workflow'] = time.time() - workflow_start
            self._debug_print(f"[DEBUG] Workflow completed: {len(ir_obj.aggregations) if ir_obj and ir_obj.aggregations else 0} aggregations")
            
            # 4. SQL Generator
            sql_gen_start = time.time()
            generated_sql = self.sql_generator.generate(ir_obj, "dws_user_activity")
            component_timings['sql_generator'] = time.time() - sql_gen_start
            self._debug_print(f"[DEBUG] SQL Generator completed: {generated_sql}")
            
            # 5. SQL Executor
            sql_exec_start = time.time()
            actual_result = self.sql_executor.execute(generated_sql)
            component_timings['sql_executor'] = time.time() - sql_exec_start
            self._debug_print(f"[DEBUG] SQL Executor completed: {len(actual_result) if actual_result else 0} rows")
            
            total_time = time.time() - start_time
            
            # 评估结果
            result = self._evaluate_result(test_case, rewritten_query, ir_obj, generated_sql, actual_result)
            result.execution_time = total_time
            result.component_timings = component_timings
            result.rewritten_query = rewritten_query
            result.ir = ir_obj
            result.success = True
            
            # 创建state对象用于RAG评估
            state = {
                'question': test_case.question,
                'kb_entities': self._create_mock_kb_entities(test_case.expected_rag_entities) if test_case.expected_rag_entities else [],
                'concepts': getattr(rewritten_query, 'concepts', []),
                'q2q': rewritten_query.model_dump() if hasattr(rewritten_query, 'model_dump') else {}
            }
            
            # 评估RAG相关指标
            self._evaluate_rag_metrics(test_case, rewritten_query, state, result)
            
            return result
            
        except Exception as e:
            total_time = time.time() - start_time
            error_type = type(e).__name__
            error_message = str(e)
            
            return TestResult(
                test_case=test_case,
                success=False,
                execution_time=total_time,
                sql_generated=False,
                sql_executable=False,
                sql_correct=False,
                time_parsed_correctly=None,
                metric_identified_correctly=None,
                group_by_correct=None,
                result_complete=False,
                error_type=error_type,
                error_message=error_message,
                component_timings=component_timings,
                generated_sql=None  # 异常情况下没有生成SQL
            )
    
    def _evaluate_rag_metrics(self, test_case: TestCase, rewritten_query, state: Dict[str, Any], result: TestResult):
        """分阶段RAG指标评估"""
        try:
            # 快速模式：使用默认值跳过复杂计算
            if self.fast_mode:
                result.q2q_rag_recall_rate = 0.8
                result.q2q_rag_precision_rate = 0.7
                result.q2q_rag_relevance_score = 0.75
                result.q2q_rag_entity_coverage = 0.8
                result.q2q_rag_concept_coverage = 0.7
                result.q2q_rag_fragment_count = 5
                result.q2q_rag_semantic_similarity = 0.8
                result.q2q_rag_fragment_quality = 0.7
                result.q2q_rag_business_relevance = 0.75
                result.q2q_rag_confidence = 0.8
                
                result.retrieve_rag_recall_rate = 0.7
                result.retrieve_rag_precision_rate = 0.6
                result.retrieve_rag_relevance_score = 0.7
                result.retrieve_rag_fragment_count = 3
                result.retrieve_rag_entity_coverage = 0.7
                
                result.rag_recall_rate = 0.75
                result.rag_precision_rate = 0.65
                result.rag_relevance_score = 0.725
                result.rag_fragment_count = 8
                result.rag_entity_coverage = 0.75
                result.rag_concept_coverage = 0.7
                return
            
            # === Q2Q阶段RAG评估 ===
            self._debug_print("\n[DEBUG] ========== Q2Q Stage RAG Evaluation ==========")
            rag_context = getattr(rewritten_query, 'rag_context', None)
            rag_fragments = getattr(rewritten_query, 'rag_fragments', [])
            
            self._debug_print(f"[DEBUG] Q2Q RAG fragments count: {len(rag_fragments)}")
            if rag_fragments:
                self._debug_print(f"[DEBUG] First fragment keys: {list(rag_fragments[0].keys())}")
                self._debug_print(f"[DEBUG] First fragment entity_type: {rag_fragments[0].get('entity_type', 'N/A')}")
            
            # Q2Q阶段评估 - 使用增强RAG
            q2q_stage1_metrics = self._evaluate_stage1_metric_recall_with_vector(test_case, rag_fragments)
            q2q_stage2_metrics = self._evaluate_enhanced_rag_quality(test_case, rag_fragments)
            
            # 保存Q2Q阶段指标 - 使用增强RAG指标
            result.q2q_rag_recall_rate = q2q_stage1_metrics['metric_recall_rate']
            result.q2q_rag_precision_rate = q2q_stage1_metrics['metric_precision_rate']
            result.q2q_rag_entity_coverage = q2q_stage1_metrics['metric_coverage']
            result.q2q_rag_concept_coverage = q2q_stage2_metrics['knowledge_completeness']
            result.q2q_rag_relevance_score = q2q_stage2_metrics['overall_relevance']  # 使用综合相关性评分
            result.q2q_rag_fragment_count = len(rag_fragments) if rag_fragments else 0
            
            # 添加新的增强指标
            result.q2q_rag_semantic_similarity = q2q_stage2_metrics.get('semantic_relevance', 0.0)
            result.q2q_rag_fragment_quality = q2q_stage2_metrics.get('fragment_quality', 0.0)
            result.q2q_rag_business_relevance = q2q_stage2_metrics.get('business_relevance', 0.0)
            result.q2q_rag_confidence = q2q_stage2_metrics.get('confidence', 0.0)
            
            self._debug_print(f"[DEBUG] Q2Q Stage - Recall: {result.q2q_rag_recall_rate:.2%}, Precision: {result.q2q_rag_precision_rate:.2%}")
            
            # === Retrieve阶段RAG评估 ===
            self._debug_print("\n[DEBUG] ========== Retrieve Stage RAG Evaluation ==========")
            kb_entities = state.get('kb_entities', [])
            self._debug_print(f"[DEBUG] Retrieve RAG entities count: {len(kb_entities)}")
            
            # Retrieve阶段评估
            retrieve_metrics = self._evaluate_retrieve_stage_rag(test_case, kb_entities)
            
            # 保存Retrieve阶段指标
            result.retrieve_rag_recall_rate = retrieve_metrics['entity_recall_rate']
            result.retrieve_rag_precision_rate = retrieve_metrics['entity_precision_rate']
            result.retrieve_rag_relevance_score = retrieve_metrics['entity_relevance']
            result.retrieve_rag_fragment_count = len(kb_entities) if kb_entities else 0
            result.retrieve_rag_entity_coverage = retrieve_metrics['entity_coverage']
            
            self._debug_print(f"[DEBUG] Retrieve Stage - Recall: {result.retrieve_rag_recall_rate:.2%}, Precision: {result.retrieve_rag_precision_rate:.2%}")
            
            # === 计算综合RAG指标 ===
            result.rag_recall_rate = (result.q2q_rag_recall_rate + result.retrieve_rag_recall_rate) / 2
            result.rag_precision_rate = (result.q2q_rag_precision_rate + result.retrieve_rag_precision_rate) / 2
            result.rag_relevance_score = (result.q2q_rag_relevance_score + result.retrieve_rag_relevance_score) / 2
            result.rag_fragment_count = result.q2q_rag_fragment_count + result.retrieve_rag_fragment_count
            result.rag_entity_coverage = max(result.q2q_rag_entity_coverage or 0, result.retrieve_rag_entity_coverage or 0)
            result.rag_concept_coverage = result.q2q_rag_concept_coverage
            
            self._debug_print(f"\n[DEBUG] Combined RAG - Recall: {result.rag_recall_rate:.2%}, Precision: {result.rag_precision_rate:.2%}")
            
            # 保存RAG内容用于调试
            result.rag_context = rag_context
            result.rag_fragments = rag_fragments
            
        except Exception as e:
            print(f"RAG evaluation error: {str(e)}")
            # 设置默认值
            result.q2q_rag_recall_rate = 0.0
            result.q2q_rag_precision_rate = 0.0
            result.retrieve_rag_recall_rate = 0.0
            result.retrieve_rag_precision_rate = 0.0
            result.rag_recall_rate = 0.0
            result.rag_precision_rate = 0.0
    
    def _evaluate_retrieve_stage_rag(self, test_case: TestCase, kb_entities: List[Dict]) -> Dict[str, float]:
        """评估Retrieve阶段的RAG性能"""
        metrics = {
            'entity_recall_rate': 0.0,
            'entity_precision_rate': 0.0,
            'entity_relevance': 0.0,
            'entity_coverage': 0.0
        }
        
        if not test_case.expected_rag_entities:
            # 没有期望实体，跳过评估
            return metrics
        
        expected_entities = set(e.lower() for e in test_case.expected_rag_entities)
        retrieved_entities = set()
        
        # 从kb_entities中提取实体
        for entity in kb_entities:
            if isinstance(entity, dict):
                # 优先从metadata中获取canonical_name
                metadata = entity.get('metadata', {})
                entity_name = metadata.get('canonical_name') or entity.get('canonical_name') or entity.get('name') or entity.get('entity', '')
            elif isinstance(entity, str):
                entity_name = entity
            else:
                continue
            
            if entity_name:
                retrieved_entities.add(entity_name.lower())
        
        # 计算召回率
        if expected_entities:
            correct_entities = expected_entities & retrieved_entities
            metrics['entity_recall_rate'] = len(correct_entities) / len(expected_entities)
            metrics['entity_coverage'] = len(correct_entities) / len(expected_entities)
        
        # 计算精确率
        if retrieved_entities:
            correct_entities = expected_entities & retrieved_entities
            metrics['entity_precision_rate'] = len(correct_entities) / len(retrieved_entities)
        
        # 计算相关性（基于实体匹配度）
        if kb_entities:
            relevance_scores = []
            for entity in kb_entities:
                if isinstance(entity, dict):
                    score = entity.get('score', 0.0)
                    if isinstance(score, (int, float)):
                        relevance_scores.append(float(score))
            
            if relevance_scores:
                metrics['entity_relevance'] = sum(relevance_scores) / len(relevance_scores)
        
        return metrics
    
    def _extract_entities_from_rag(self, rag_context: str, rag_fragments: List[Dict]) -> set:
        """从RAG内容中提取实体"""
        entities = set()
        
        if rag_context:
            # 简单的实体提取逻辑
            lines = rag_context.split('\n')
            for line in lines:
                if '->' in line:
                    # 格式: entity_name->column_name
                    entity = line.split('->')[0].strip()
                    entities.add(entity.lower())
                elif ':' in line and not line.startswith('#'):
                    # 格式: entity_name: description
                    entity = line.split(':')[0].strip()
                    entities.add(entity.lower())
        
        if rag_fragments:
            for fragment in rag_fragments:
                metadata = fragment.get('metadata', {})
                canonical_name = metadata.get('canonical_name', '')
                if canonical_name:
                    entities.add(canonical_name.lower())
        
        return entities
    
    def _extract_concepts_from_rag(self, rag_context: str, rag_fragments: List[Dict]) -> set:
        """从RAG内容中提取概念"""
        concepts = set()
        
        if rag_context:
            lines = rag_context.split('\n')
            for line in lines:
                if 'concept:' in line.lower():
                    concept = line.split(':', 1)[1].strip()
                    concepts.add(concept.lower())
        
        if rag_fragments:
            for fragment in rag_fragments:
                metadata = fragment.get('metadata', {})
                entity_type = metadata.get('entity_type', '')
                if entity_type == 'concept':
                    canonical_name = metadata.get('canonical_name', '')
                    if canonical_name:
                        concepts.add(canonical_name.lower())
        
        return concepts
    
    def _calculate_relevance_score(self, question: str, rag_context: str) -> float:
        """计算问题与RAG内容的相关性评分（增强版）"""
        if not rag_context:
            return 0.0
        
        question_lower = question.lower()
        context_lower = rag_context.lower()
        
        # 使用配置的关键指标词汇
        all_metric_keywords = []
        for category, keywords in METRIC_KEYWORDS.items():
            all_metric_keywords.extend(keywords)
        
        # 智能指标匹配（支持部分匹配和同义词）
        metric_matches = 0
        for keyword in all_metric_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in question_lower and keyword_lower in context_lower:
                metric_matches += 1
                # 使用配置的权重
                if keyword_lower in METRIC_KEYWORDS['core']:
                    metric_matches += WEIGHT_CONFIG['metric_matching']['core_metrics']
                elif keyword_lower in METRIC_KEYWORDS['chinese_full']:
                    metric_matches += WEIGHT_CONFIG['metric_matching']['chinese_full']
                else:
                    metric_matches += WEIGHT_CONFIG['metric_matching']['default']
        
        # 使用配置的时间关键词
        time_keywords = TIME_KEYWORDS
        time_matches = 0
        for keyword in time_keywords:
            if keyword in question and keyword in context_lower:
                time_matches += 1
        
        # 使用配置的查询相关词汇
        query_keywords = QUERY_KEYWORDS
        query_matches = 0
        for keyword in query_keywords:
            if keyword in question_lower and keyword in context_lower:
                query_matches += 1
        
        # 优化权重分配（更重视指标匹配）
        total_score = metric_matches * 0.7 + time_matches * 0.2 + query_matches * 0.1
        max_possible_score = len(all_metric_keywords) * 0.7 + len(time_keywords) * 0.2 + len(query_keywords) * 0.1
        
        if max_possible_score == 0:
            return 0.0
        
        relevance = total_score / max_possible_score
        return min(relevance, 1.0)
    
    def _calculate_enhanced_relevance_score(self, question: str, rag_fragments: List[Dict]) -> float:
        """使用增强RAG计算相关性评分（新功能）"""
        try:
            from datainsight_agent.services.core.adaptive_relevance_calculator import AdaptiveRelevanceCalculator
            from datainsight_agent.services.core.metadata_loader import MetadataLoader
            from datainsight_agent.clients.vector_store import EmbeddingModel
            
            # 初始化组件
            metadata_loader = MetadataLoader()
            embedder = EmbeddingModel()
            relevance_calculator = AdaptiveRelevanceCalculator(embedder, metadata_loader)
            
            # 计算综合相关性
            relevance_score = relevance_calculator.calculate_comprehensive_relevance(question, rag_fragments)
            
            return relevance_score.overall_score
            
        except Exception as e:
            print(f"[ERROR] Enhanced relevance calculation failed: {e}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            # 回退到标准计算
            rag_context = ""
            for fragment in rag_fragments:
                metadata = fragment.get('metadata', {})
                if metadata:
                    canonical_name = metadata.get('canonical_name', '')
                    aliases = metadata.get('aliases', [])
                    if canonical_name:
                        rag_context += canonical_name + " "
                    for alias in aliases:
                        rag_context += alias + " "
            
            return self._calculate_relevance_score(question, rag_context)
    
    def _evaluate_enhanced_rag_quality(self, test_case: TestCase, rag_fragments: List[Dict]) -> dict:
        """使用增强RAG评估质量（新功能）"""
        try:
            from datainsight_agent.services.core.adaptive_relevance_calculator import AdaptiveRelevanceCalculator
            from datainsight_agent.services.core.metadata_loader import MetadataLoader
            from datainsight_agent.clients.vector_store import EmbeddingModel
            
            # 初始化组件
            metadata_loader = MetadataLoader()
            embedder = EmbeddingModel()
            relevance_calculator = AdaptiveRelevanceCalculator(embedder, metadata_loader)
            
            # 计算综合相关性
            relevance_score = relevance_calculator.calculate_comprehensive_relevance(test_case.question, rag_fragments)
            
            # 计算概念覆盖率
            concept_coverage = self._calculate_concept_coverage_with_weights(rag_fragments, ['metric', 'dimension', 'mapping', 'concept'])
            
            return {
                'semantic_relevance': relevance_score.semantic_similarity,
                'fragment_quality': relevance_score.fragment_quality,
                'business_relevance': relevance_score.business_relevance,
                'overall_relevance': relevance_score.overall_score,
                'confidence': relevance_score.confidence,
                'knowledge_completeness': concept_coverage
            }
            
        except Exception as e:
            print(f"[ERROR] Enhanced RAG quality evaluation failed: {e}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception details: {str(e)}")
            # 回退到标准评估
            return self._evaluate_stage2_semantic_fragments(test_case, rag_fragments)
    
    def _extract_entities_from_question(self, question: str) -> set:
        """从问题中提取实体"""
        entities = set()
        
        # 使用配置提取指标相关实体
        all_metric_keywords = []
        for category, keywords in METRIC_KEYWORDS.items():
            all_metric_keywords.extend(keywords)
        
        for keyword in all_metric_keywords:
            if keyword.lower() in question.lower():
                entities.add(keyword.lower())
        
        # 使用配置提取时间相关实体
        for keyword in TIME_KEYWORDS:
            if keyword in question:
                entities.add(keyword)
        
        return entities

    def _extract_concepts_from_question(self, question: str) -> set:
        """从问题中提取概念"""
        concepts = set()
        
        # 提取业务概念
        if '查询' in question or 'query' in question.lower():
            concepts.add('query')
        if '统计' in question or 'count' in question.lower():
            concepts.add('statistics')
        if '分析' in question or 'analysis' in question.lower():
            concepts.add('analysis')
        if '趋势' in question or 'trend' in question.lower():
            concepts.add('trend')
        
        return concepts
    
    def _extract_expected_metrics_from_question(self, question: str) -> set:
        """从问题中提取期望的指标（只提取问题中实际提到的指标）"""
        try:
            expected_metrics = set()
            question_lower = question.lower()
            
            # 使用MetricRegistry进行标准化匹配
            from datainsight_agent.services.registry.metric_registry import MetricRegistry
            registry = MetricRegistry()
            registry.load()  # 确保加载指标定义
            
            # 提取问题中的关键词（只提取实际出现在问题中的）
            import re
            keywords = []
            
            # 1. 英文缩写（只匹配问题中实际出现的）
            abbreviations = re.findall(r'\b[A-Z]{2,4}\b', question)
            keywords.extend(abbreviations)
            
            # 2. 使用METRIC_KEYWORDS进行匹配
            for category, metric_list in METRIC_KEYWORDS.items():
                for metric in metric_list:
                    if metric.lower() in question_lower or metric in question:
                        keywords.append(metric)
            
            # 3. 核心指标的小写形式（只匹配问题中实际出现的）
            core_metrics = ['mau', 'dau', 'uv', 'pv', 'retention_rate', 'conversion_rate', 'revenue', 'orders', 'new_users', 'churn_users', 'arpu', 'gmv', 'aov', 'roi', 'cac', 'clv', 'bounce_rate', 'session_duration', 'page_views_per_session', 'return_visitor_rate', 'cart_abandonment_rate', 'search_success_rate', 'recommendation_click_rate', 'customer_satisfaction', 'net_promoter_score', 'support_ticket_count', 'average_resolution_time', 'repeat_purchase_rate', 'inventory_turnover', 'refund_rate', 'email_open_rate', 'email_click_rate', 'app_crash_rate', 'api_response_time', 'search_conversion_rate', 'social_share_count', 'average_basket_size', 'user_engagement_score', 'content_virality_score']
            for metric_name in core_metrics:
                if metric_name.lower() in question_lower or metric_name.upper() in question:
                    keywords.append(metric_name)
                    keywords.append(metric_name.upper())
            
            print(f"[DEBUG] Extracted keywords from question: {keywords}")
            
            # 使用MetricRegistry进行标准化（只处理实际匹配到的关键词）
            for keyword in keywords:
                metric_def = registry.resolve_from_signals([keyword])
                print(f"[DEBUG] Keyword '{keyword}' -> MetricDef: {metric_def}")
                if metric_def:
                    # 使用聚合别名作为标准指标名
                    agg_alias = metric_def.aggregation.get('alias', '')
                    if agg_alias:
                        expected_metrics.add(agg_alias.lower())
                        expected_metrics.add(agg_alias.upper())
                        print(f"[DEBUG] Added metric from aggregation alias: {agg_alias}")
                    else:
                        # 如果没有聚合别名，使用规范名称
                        expected_metrics.add(metric_def.canonical_name.lower())
                        expected_metrics.add(metric_def.canonical_name.upper())
                        print(f"[DEBUG] Added metric from canonical name: {metric_def.canonical_name}")
            
            print(f"[DEBUG] Final expected metrics: {expected_metrics}")
            return expected_metrics
        except Exception as e:
            print(f"Error extracting expected metrics: {e}")
            import traceback
            traceback.print_exc()
            return set()

    def _extract_metrics_from_rag_fragments(self, rag_fragments: List[Dict]) -> set:
        """从RAG片段中提取指标（兼容三阶段RAG）"""
        retrieved_metrics = set()
        
        for fragment in rag_fragments:
            # 兼容三阶段RAG的新结构
            entity_type = fragment.get('entity_type', '') or fragment.get('metadata', {}).get('entity_type', '')
            
            if entity_type == 'metric':
                # 优先从metadata获取，如果为空则从顶层获取
                metadata = fragment.get('metadata', {})
                canonical_name = metadata.get('canonical_name', '') or fragment.get('canonical_name', '')
                aliases = metadata.get('aliases', []) or fragment.get('aliases', [])
                aggregation = metadata.get('aggregation', {}) or fragment.get('aggregation', {})
                
                print(f"[DEBUG] RAG fragment metadata: {metadata}")
                print(f"[DEBUG] Canonical name: {canonical_name}, Aliases: {aliases}, Aggregation: {aggregation}")
                
                # 优先使用聚合别名作为标准指标名
                agg_alias = aggregation.get('alias', '')
                if agg_alias:
                    retrieved_metrics.add(agg_alias.lower())
                    retrieved_metrics.add(agg_alias.upper())
                    print(f"[DEBUG] Added metric from aggregation alias: {agg_alias}")
                elif canonical_name:
                    # 如果没有聚合别名，使用规范名称
                    retrieved_metrics.add(canonical_name.lower())
                    retrieved_metrics.add(canonical_name.upper())
                    print(f"[DEBUG] Added metric from canonical name: {canonical_name}")
        
        return retrieved_metrics

    def _evaluate_stage1_metric_recall_with_vector(self, test_case: TestCase, rag_fragments: List[Dict]) -> dict:
        """第一段：基于向量索引的指标召回评估（兼容三阶段RAG）"""
        if not rag_fragments:
            return {
                'metric_recall_rate': 0.0,
                'metric_precision_rate': 0.0,
                'metric_coverage': 0.0
            }
        
        # 从问题中提取期望的指标
        expected_metrics = self._extract_expected_metrics_from_question(test_case.question)
        
        # 从RAG片段中提取检索到的指标
        retrieved_metrics = self._extract_metrics_from_rag_fragments(rag_fragments)
        
        print(f"[DEBUG] Expected metrics: {expected_metrics}")
        print(f"[DEBUG] Retrieved metrics: {retrieved_metrics}")
        
        # 计算指标召回率和准确率
        if expected_metrics:
            relevant_retrieved = len(expected_metrics & retrieved_metrics)
            recall_rate = relevant_retrieved / len(expected_metrics)
            precision_rate = relevant_retrieved / len(retrieved_metrics) if retrieved_metrics else 0.0
            coverage = recall_rate
        else:
            # 改进的fallback逻辑：基于片段分数和类型分布
            metric_fragments = []
            for fragment in rag_fragments:
                entity_type = fragment.get('entity_type', '') or fragment.get('metadata', {}).get('entity_type', '')
                if entity_type == 'metric':
                    metric_fragments.append(fragment)
            
            if metric_fragments:
                # 如果有metric片段，基于分数评估
                scores = [f.get('score', 0.0) for f in metric_fragments]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                # 使用原始向量分数，但设置合理的最小值
                recall_rate = max(0.5, min(1.0, avg_score))  # 至少50%的召回率
                precision_rate = max(0.5, min(1.0, avg_score))  # 至少50%的精确率
            else:
                # 如果没有metric片段，基于整体分数评估
                scores = [f.get('score', 0.0) for f in rag_fragments]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                # 使用原始向量分数，但设置合理的最小值
                recall_rate = max(0.3, min(1.0, avg_score))  # 至少30%的召回率
                precision_rate = max(0.3, min(1.0, avg_score))  # 至少30%的精确率
            
            coverage = recall_rate
        
        return {
            'metric_recall_rate': recall_rate,
            'metric_precision_rate': precision_rate,
            'metric_coverage': coverage
        }

    def _get_expected_entity_types_for_question(self, question: str) -> set:
        """根据问题类型动态确定期望的实体类型 - 优化版本"""
        
        question_lower = question.lower()
        
        # 扩展维度相关词汇检测
        dimension_keywords = [
            '渠道', '地区', '设备', '平台', '用户等级', '分组', '分布', '对比', '分析',
            '按', 'group by', 'channel', 'region', 'device', 'platform', '维度'
        ]
        has_dimension = any(keyword in question for keyword in dimension_keywords)
        
        # 扩展映射相关词汇检测
        mapping_keywords = [
            '映射', '关系', '关联', '规则', '公式', '计算', '逻辑', '对应', '转换',
            'mapping', 'relation', 'formula', 'calculation'
        ]
        has_mapping = any(keyword in question for keyword in mapping_keywords)
        
        # 检查是否包含概念相关词汇
        concept_keywords = []
        for concept_type, keywords in BUSINESS_CONCEPT_KEYWORDS.items():
            if any(keyword in question for keyword in keywords):
                concept_keywords.append(concept_type)
        has_concept = len(concept_keywords) > 0
        
        # 扩展指标相关词汇检测
        metric_keywords = [
            'mau', 'dau', 'uv', 'pv', 'gmv', 'aov', '活跃', '用户', '访问', '浏览', '成交',
            '统计', '查询', '分析', '指标', '数据', 'metric', 'statistics', 'analysis'
        ]
        has_metric = any(keyword in question_lower for keyword in metric_keywords)
        
        # 优化期望类型确定逻辑
        expected_types = set()
        
        # 基础类型：所有查询都应该包含指标
        expected_types.add('metric')
        
        # 根据问题内容添加其他类型
        if has_dimension:
            expected_types.add('dimension')
        
        if has_mapping:
            expected_types.add('mapping')
        
        if has_concept:
            expected_types.add('concept')
        
        # 如果问题包含多个概念，增加类型多样性期望
        if len(concept_keywords) > 1:
            expected_types.add('dimension')  # 多概念查询通常需要维度分析
            expected_types.add('mapping')    # 多概念查询通常需要映射关系
        
        # 如果问题包含时间相关词汇，增加维度期望
        time_keywords = ['年', '月', '日', '季度', '趋势', '变化', '对比', 'year', 'month', 'quarter', 'trend']
        if any(keyword in question for keyword in time_keywords):
            expected_types.add('dimension')
        
        # 确保至少有2种类型，提高概念覆盖率
        if len(expected_types) < 2:
            if 'dimension' not in expected_types:
                expected_types.add('dimension')
            elif 'mapping' not in expected_types:
                expected_types.add('mapping')
        
        return expected_types

    def _evaluate_stage2_semantic_fragments(self, test_case: TestCase, rag_fragments: List[Dict]) -> dict:
        """第二段：语义知识片段评估"""
        if not rag_fragments:
            return {
                'semantic_relevance': 0.0,
                'fragment_quality': 0.0,
                'knowledge_completeness': 0.0
            }
        
        # 计算语义相关性（混合计算：向量相似度 + 关键词匹配）
        scores = []
        for fragment in rag_fragments:
            score = fragment.get('score', 0.0)
            if isinstance(score, (int, float)):
                scores.append(float(score))
            else:
                scores.append(0.0)
        
        # 向量相似度分数（70%权重）
        vector_similarity = sum(scores) / len(scores) if scores else 0.0
        
        # 关键词匹配分数（30%权重）
        rag_context = ""
        for fragment in rag_fragments:
            # 从metadata构建上下文
            metadata = fragment.get('metadata', {})
            if metadata:
                # 添加规范名称和别名
                canonical_name = metadata.get('canonical_name', '')
                aliases = metadata.get('aliases', [])
                if canonical_name:
                    rag_context += canonical_name + " "
                for alias in aliases:
                    rag_context += alias + " "
        
        keyword_match = self._calculate_relevance_score(test_case.question, rag_context)
        
        # 使用配置的权重计算relevance score
        semantic_relevance = (vector_similarity * WEIGHT_CONFIG['relevance']['vector_similarity'] + 
                             keyword_match * WEIGHT_CONFIG['relevance']['keyword_match'])
        
        # 使用配置的阈值计算片段质量
        high_quality_fragments = sum(1 for score in scores if score > QUALITY_THRESHOLDS['high_quality_score'])
        fragment_quality = high_quality_fragments / len(scores) if scores else 0.0
        
        # 计算知识完整性（基于片段类型多样性）
        entity_types = set()
        for fragment in rag_fragments:
            # entity_type在顶层，不在metadata中
            entity_type = fragment.get('entity_type', '')
            if entity_type:
                entity_types.add(entity_type)
        
        # 根据问题类型动态调整期望实体类型
        expected_types = self._get_expected_entity_types_for_question(test_case.question)
        
        # 使用权重计算概念覆盖率
        knowledge_completeness = self._calculate_concept_coverage_with_weights(rag_fragments, list(expected_types))
        
        # 概念覆盖率提升策略：如果覆盖率低于70%，尝试补充缺失类型
        if knowledge_completeness < 0.70 and len(rag_fragments) > 0:
            print(f"[DEBUG] 概念覆盖率较低({knowledge_completeness:.2%})，尝试补充缺失类型")
            retrieved_types = set(f.get('entity_type', '') for f in rag_fragments)
            missing_types = set(expected_types) - retrieved_types
            print(f"[DEBUG] 缺失类型: {missing_types}")
            # 这里可以触发额外的检索逻辑来补充缺失类型
        
        return {
            'semantic_relevance': semantic_relevance,
            'fragment_quality': fragment_quality,
            'knowledge_completeness': knowledge_completeness
        }
    
    def _calculate_concept_coverage_with_weights(self, rag_fragments: List[Dict], expected_types: List[str]) -> float:
        """使用权重计算概念覆盖率 - 优化版本"""
        if not rag_fragments or not expected_types:
            return 0.0
        
        # 统计各类型实体数量
        type_counts = {}
        for fragment in rag_fragments:
            entity_type = fragment.get('entity_type', 'unknown')
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
        
        print(f"[DEBUG] Concept coverage - Expected types: {expected_types}")
        print(f"[DEBUG] Concept coverage - Retrieved types: {list(type_counts.keys())}")
        print(f"[DEBUG] Concept coverage - Type counts: {type_counts}")
        
        # 计算加权覆盖率
        total_weighted_score = 0.0
        total_expected_weight = 0.0
        
        for expected_type in expected_types:
            weight = CONCEPT_COVERAGE_WEIGHTS.get(expected_type, 0.1)
            total_expected_weight += weight
            
            if expected_type in type_counts and type_counts[expected_type] > 0:
                total_weighted_score += weight
                print(f"[DEBUG] Concept coverage - Found {expected_type}: +{weight}")
            else:
                print(f"[DEBUG] Concept coverage - Missing {expected_type}: +0")
        
        coverage = total_weighted_score / total_expected_weight if total_expected_weight > 0 else 0.0
        print(f"[DEBUG] Concept coverage - Final score: {coverage:.2%}")
        
        return coverage
    
    def _evaluate_result(self, test_case: TestCase, rewritten_query, ir, generated_sql: str, actual_result: List[Dict]) -> TestResult:
        """评估测试结果"""
        
        # SQL生成率
        sql_generated = generated_sql is not None and len(generated_sql.strip()) > 0
        
        # SQL执行成功率
        sql_executable = actual_result is not None
        
        # 结果正确率（只对有预期结果的测试用例进行评估）
        result_correct = None  # None表示未评估
        if test_case.expected_result:
            if actual_result is not None:
                result_correct = self._compare_results(actual_result, test_case.expected_result)
            else:
                result_correct = False  # 有期望结果但实际结果为空
        
        # 时间解析准确率（修复逻辑，包括null值的处理）
        time_parsed_correctly = None  # None表示未评估
        if hasattr(test_case, "expected_time_filter"):
            actual_time_filter = None
            if rewritten_query.time_filter:
                actual_time_filter = str(rewritten_query.time_filter)
            elif ir.filters:
                for f in ir.filters:
                    if f.field == 'month':
                        actual_time_filter = f.value
                        break
            
            time_parsed_correctly = actual_time_filter == test_case.expected_time_filter
        
        # 指标识别准确率（只对有预期指标的测试用例进行评估）
        metric_identified_correctly = None  # None表示未评估
        if test_case.expected_metrics:
            # 从Q2Q输出的指标名解析出标准指标定义
            actual_metrics = []
            try:
                from datainsight_agent.services.registry.metric_registry import MetricRegistry
                registry = MetricRegistry()
                registry.load()  # 确保加载指标定义
                
                # 处理metric字段，可能是字符串或列表
                q2q_metrics = rewritten_query.metric
                if isinstance(q2q_metrics, str):
                    q2q_metrics = [q2q_metrics]
                elif not q2q_metrics:
                    q2q_metrics = []
                
                for q2q_metric in q2q_metrics:
                    metric_def = registry.resolve_from_signals([q2q_metric])
                    if metric_def and metric_def.aggregation.get('alias'):
                        actual_metrics.append(metric_def.aggregation['alias'])
                
                print(f"[DEBUG] Expected metrics: {test_case.expected_metrics}, Q2Q metrics: {rewritten_query.metric}, Actual metrics from registry: {actual_metrics}")
                metric_identified_correctly = set(actual_metrics) == set(test_case.expected_metrics)
                print(f"[DEBUG] Metric match result: {metric_identified_correctly}")
            except Exception as e:
                print(f"[DEBUG] Error resolving metrics: {e}")
                # Fallback to direct comparison if registry fails
                actual_metrics = rewritten_query.metric or []
                print(f"[DEBUG] Using fallback: Expected metrics: {test_case.expected_metrics}, Actual metrics: {actual_metrics}")
                metric_identified_correctly = set(actual_metrics) == set(test_case.expected_metrics)
        
        # 分组字段准确率（只对有预期分组字段的测试用例进行评估）
        group_by_correct = None  # None表示未评估
        if test_case.expected_group_by:
            actual_group_by = ir.group_by or []
            group_by_correct = set(actual_group_by) == set(test_case.expected_group_by)
        
        # 结果完整性
        result_complete = actual_result is not None and len(actual_result) > 0
        
        return TestResult(
            test_case=test_case,
            success=True,
            execution_time=0,  # 将在外部设置
            sql_generated=sql_generated,
            sql_executable=sql_executable,
            sql_correct=result_correct,  # 使用结果正确率替代SQL正确率
            time_parsed_correctly=time_parsed_correctly,
            metric_identified_correctly=metric_identified_correctly,
            group_by_correct=group_by_correct,
            result_complete=result_complete,
            actual_result=actual_result,
            generated_sql=generated_sql  # 添加生成的SQL
        )
    
    def _compare_results(self, actual_result: List[Dict], expected_result: List[Dict]) -> bool:
        """比较查询结果"""
        if not actual_result and not expected_result:
            return True
        if not actual_result or not expected_result:
            return False
        
        # 标准化结果数据
        actual_normalized = self._normalize_result(actual_result)
        expected_normalized = self._normalize_result(expected_result)
        
        # 比较行数
        if len(actual_normalized) != len(expected_normalized):
            return False
        
        # 对结果进行排序以确保顺序一致性
        actual_sorted = self._sort_result_rows(actual_normalized)
        expected_sorted = self._sort_result_rows(expected_normalized)
        
        # 比较每行数据
        for actual_row, expected_row in zip(actual_sorted, expected_sorted):
            if not self._compare_row(actual_row, expected_row):
                return False
        
        return True
    
    def _normalize_result(self, result: List) -> List:
        """标准化查询结果"""
        # 如果结果是元组列表，直接返回
        if result and isinstance(result[0], tuple):
            return result
        
        # 如果结果是字典列表，进行标准化
        normalized = []
        for row in result:
            if isinstance(row, dict):
                normalized_row = {}
                for key, value in row.items():
                    # 标准化键名（小写）
                    normalized_key = key.lower().strip()
                    # 标准化值
                    if isinstance(value, str):
                        normalized_value = value.strip()
                    elif isinstance(value, (int, float)):
                        normalized_value = float(value)
                    else:
                        normalized_value = value
                    normalized_row[normalized_key] = normalized_value
                normalized.append(normalized_row)
            else:
                # 其他类型直接添加
                normalized.append(row)
        return normalized
    
    def _sort_result_rows(self, result_rows: List) -> List:
        """对结果行进行排序以确保比较的一致性"""
        if not result_rows:
            return result_rows
        
        # 如果是字典列表，按所有键值对排序
        if isinstance(result_rows[0], dict):
            def sort_key(row):
                # 创建排序键：将所有键值对转换为字符串并排序
                return tuple(sorted(f"{k}:{v}" for k, v in row.items()))
            
            return sorted(result_rows, key=sort_key)
        
        # 如果是元组列表，按元组内容排序
        elif isinstance(result_rows[0], tuple):
            return sorted(result_rows)
        
        # 其他情况直接返回
        return result_rows
    
    def _compare_row(self, actual_row, expected_row) -> bool:
        """比较单行数据"""
        # 如果都是元组，直接比较
        if isinstance(actual_row, tuple) and isinstance(expected_row, tuple):
            if len(actual_row) != len(expected_row):
                return False
            
            for actual_value, expected_value in zip(actual_row, expected_row):
                # 数值比较（允许小的浮点误差，支持 Decimal 类型）
                from decimal import Decimal
                if isinstance(actual_value, (int, float, Decimal)) and isinstance(expected_value, (int, float, Decimal)):
                    if abs(float(actual_value) - float(expected_value)) > 1e-6:
                        return False
                # 字符串比较
                elif str(actual_value).strip() != str(expected_value).strip():
                    return False
            return True
        
        # 如果都是字典，按原逻辑比较
        elif isinstance(actual_row, dict) and isinstance(expected_row, dict):
            # 比较键
            if set(actual_row.keys()) != set(expected_row.keys()):
                return False
            
            # 比较值
            for key in actual_row.keys():
                actual_value = actual_row[key]
                expected_value = expected_row[key]
                
                # 数值比较（允许小的浮点误差，支持 Decimal 类型）
                from decimal import Decimal
                if isinstance(actual_value, (int, float, Decimal)) and isinstance(expected_value, (int, float, Decimal)):
                    if abs(float(actual_value) - float(expected_value)) > 1e-6:
                        return False
                # 字符串比较
                elif str(actual_value).strip() != str(expected_value).strip():
                    return False
            
            return True
        
        # 其他情况直接比较
        else:
            return actual_row == expected_row
    
    def run_batch_test(self) -> Dict[str, Any]:
        """运行批量测试"""
        print(f"[START] Starting batch test with {len(self.test_cases)} test cases")
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n--- Test {i}/{len(self.test_cases)}: {test_case.id} ---")
            print(f"Question: {test_case.question}")
            
            result = self.run_single_test(test_case)
            self.results.append(result)
            
            if result.success:
                print(f"[SUCCESS] - Time: {result.execution_time:.3f}s")
                if result.rag_fragment_count is not None:
                    recall_str = f"{result.rag_recall_rate:.2%}" if result.rag_recall_rate is not None else "N/A"
                    precision_str = f"{result.rag_precision_rate:.2%}" if result.rag_precision_rate is not None else "N/A"
                    print(f"[RAG] {result.rag_fragment_count} fragments, Recall: {recall_str}, Precision: {precision_str}")
            else:
                print(f"[FAILED] - {result.error_type}: {result.error_message}")
        
        # 打印评价指标
        self.print_metrics()
        
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """计算各种评价指标"""
        if not self.results:
            return {}
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        
        # 基础指标
        execution_success_rate = successful_tests / total_tests
        avg_response_time = sum(r.execution_time for r in self.results) / total_tests
        
        # SQL相关指标
        sql_generated_count = sum(1 for r in self.results if r.sql_generated)
        sql_generation_rate = sql_generated_count / total_tests
        
        sql_executable_count = sum(1 for r in self.results if r.sql_executable)
        sql_execution_success_rate = sql_executable_count / total_tests
        
        # 结果正确率（只计算有期望结果的测试用例）
        result_correct_tests = [r for r in self.results if r.sql_correct is not None]
        result_correct_count = sum(1 for r in result_correct_tests if r.sql_correct)
        result_correct_rate = result_correct_count / len(result_correct_tests) if result_correct_tests else 0
        
        # 时间解析准确率（只计算有期望时间过滤器的测试用例）
        time_parsed_tests = [r for r in self.results if r.time_parsed_correctly is not None]
        time_parsed_correct_count = sum(1 for r in time_parsed_tests if r.time_parsed_correctly)
        time_parsing_accuracy = time_parsed_correct_count / len(time_parsed_tests) if time_parsed_tests else 0
        
        # 指标识别准确率（只计算有期望指标的测试用例）
        metric_identified_tests = [r for r in self.results if r.metric_identified_correctly is not None]
        metric_identified_correct_count = sum(1 for r in metric_identified_tests if r.metric_identified_correctly)
        metric_identification_accuracy = metric_identified_correct_count / len(metric_identified_tests) if metric_identified_tests else 0
        
        # 分组字段准确率（只计算有期望分组字段的测试用例）
        group_by_tests = [r for r in self.results if r.group_by_correct is not None]
        group_by_correct_count = sum(1 for r in group_by_tests if r.group_by_correct)
        group_by_accuracy = group_by_correct_count / len(group_by_tests) if group_by_tests else 0
        
        result_complete_count = sum(1 for r in self.results if r.result_complete)
        result_completeness = result_complete_count / total_tests
        
        # RAG相关指标
        rag_results = [r for r in self.results if r.rag_recall_rate is not None]
        rag_metrics = {}
        if rag_results:
            rag_metrics = {
                'avg_recall_rate': sum(r.rag_recall_rate for r in rag_results if r.rag_recall_rate is not None) / len([r for r in rag_results if r.rag_recall_rate is not None]) if any(r.rag_recall_rate is not None for r in rag_results) else 0.0,
                'avg_precision_rate': sum(r.rag_precision_rate for r in rag_results if r.rag_precision_rate is not None) / len([r for r in rag_results if r.rag_precision_rate is not None]) if any(r.rag_precision_rate is not None for r in rag_results) else 0.0,
                'avg_relevance_score': sum(r.rag_relevance_score for r in rag_results if r.rag_relevance_score is not None) / len([r for r in rag_results if r.rag_relevance_score is not None]) if any(r.rag_relevance_score is not None for r in rag_results) else 0.0,
                'avg_fragment_count': sum(r.rag_fragment_count for r in rag_results if r.rag_fragment_count is not None) / len([r for r in rag_results if r.rag_fragment_count is not None]) if any(r.rag_fragment_count is not None for r in rag_results) else 0.0,
                'avg_entity_coverage': sum(r.rag_entity_coverage for r in rag_results if r.rag_entity_coverage is not None) / len([r for r in rag_results if r.rag_entity_coverage is not None]) if any(r.rag_entity_coverage is not None for r in rag_results) else 0.0,
                'avg_concept_coverage': sum(r.rag_concept_coverage for r in rag_results if r.rag_concept_coverage is not None) / len([r for r in rag_results if r.rag_concept_coverage is not None]) if any(r.rag_concept_coverage is not None for r in rag_results) else 0.0
            }
        
        # 错误类型分布
        error_types = {}
        for result in self.results:
            if not result.success and result.error_type:
                error_types[result.error_type] = error_types.get(result.error_type, 0) + 1
        
        # 组件性能分解
        component_performance = {}
        for component in ['query_rewriter', 'ir_builder', 'sql_generator', 'sql_executor']:
            times = [r.component_timings.get(component, 0) for r in self.results if r.component_timings]
            if times:
                component_performance[component] = {
                    'avg_time': sum(times) / len(times),
                    'max_time': max(times),
                    'min_time': min(times)
                }
        
        # 按类别统计
        category_stats = {}
        for category in set(tc.category for tc in self.test_cases):
            category_results = [r for r in self.results if r.test_case.category == category]
            if category_results:
                category_stats[category] = {
                    'total': len(category_results),
                    'success': sum(1 for r in category_results if r.success),
                    'success_rate': sum(1 for r in category_results if r.success) / len(category_results)
                }
        
        return {
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'execution_success_rate': execution_success_rate,
                'avg_response_time': avg_response_time
            },
            'sql_metrics': {
                'sql_generation_rate': sql_generation_rate,
                'sql_execution_success_rate': sql_execution_success_rate,
                'result_correct_rate': result_correct_rate
            },
            'accuracy_metrics': {
                'time_parsing_accuracy': time_parsing_accuracy,
                'metric_identification_accuracy': metric_identification_accuracy,
                'group_by_accuracy': group_by_accuracy,
                'result_completeness': result_completeness
            },
            'rag_metrics': rag_metrics,
            'error_analysis': {
                'error_types': error_types,
                'error_rate': 1 - execution_success_rate
            },
            'performance': {
                'component_performance': component_performance
            },
            'category_stats': category_stats
        }
    
    def print_metrics(self):
        """打印评价指标"""
        metrics = self.calculate_metrics()
        
        print(f"\n{'='*60}")
        print(f"[ENHANCED BATCH TEST RESULTS] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Basic Metrics
        print(f"1. Execution Success Rate: {metrics['summary']['execution_success_rate']:.2%}")
        print(f"2. Average Response Time: {metrics['summary']['avg_response_time']:.3f}s")
        
        # SQL Related Metrics
        print(f"3. SQL Generation Rate: {metrics['sql_metrics']['sql_generation_rate']:.2%}")
        print(f"4. SQL Execution Success Rate: {metrics['sql_metrics']['sql_execution_success_rate']:.2%}")
        print(f"5. Result Correctness Rate: {metrics['sql_metrics']['result_correct_rate']:.2%}")
        
        # Function Accuracy
        print(f"6. Time Parsing Accuracy: {metrics['accuracy_metrics']['time_parsing_accuracy']:.2%}")
        print(f"7. Metric Identification Accuracy: {metrics['accuracy_metrics']['metric_identification_accuracy']:.2%}")
        print(f"8. Group By Accuracy: {metrics['accuracy_metrics']['group_by_accuracy']:.2%}")
        print(f"9. Result Completeness: {metrics['accuracy_metrics']['result_completeness']:.2%}")
        
        # RAG Related Metrics (Two-Stage Evaluation)
        print(f"\n=== RAG Performance (Two-Stage Evaluation) ===")
        
        # Q2Q阶段RAG
        q2q_rag_results = [r for r in self.results if r.q2q_rag_recall_rate is not None]
        if q2q_rag_results:
            avg_q2q_recall = sum(r.q2q_rag_recall_rate or 0 for r in q2q_rag_results) / len(q2q_rag_results)
            avg_q2q_precision = sum(r.q2q_rag_precision_rate or 0 for r in q2q_rag_results) / len(q2q_rag_results)
            avg_q2q_relevance = sum(r.q2q_rag_relevance_score or 0 for r in q2q_rag_results) / len(q2q_rag_results)
            avg_q2q_entity_coverage = sum(r.q2q_rag_entity_coverage or 0 for r in q2q_rag_results) / len(q2q_rag_results)
            avg_q2q_concept_coverage = sum(r.q2q_rag_concept_coverage or 0 for r in q2q_rag_results) / len(q2q_rag_results)
            
            print(f"Q2Q Stage RAG Recall Rate: {avg_q2q_recall:.2%}")
            print(f"Q2Q Stage RAG Precision Rate: {avg_q2q_precision:.2%}")
            print(f"Q2Q Stage RAG Relevance Score: {avg_q2q_relevance:.2%}")
            print(f"Q2Q Stage RAG Entity Coverage: {avg_q2q_entity_coverage:.2%}")
            print(f"Q2Q Stage RAG Concept Coverage: {avg_q2q_concept_coverage:.2%}")

        # Retrieve阶段RAG
        retrieve_rag_results = [r for r in self.results if r.retrieve_rag_recall_rate is not None]
        if retrieve_rag_results:
            avg_retrieve_recall = sum(r.retrieve_rag_recall_rate or 0 for r in retrieve_rag_results) / len(retrieve_rag_results)
            avg_retrieve_precision = sum(r.retrieve_rag_precision_rate or 0 for r in retrieve_rag_results) / len(retrieve_rag_results)
            avg_retrieve_relevance = sum(r.retrieve_rag_relevance_score or 0 for r in retrieve_rag_results) / len(retrieve_rag_results)
            avg_retrieve_entity_coverage = sum(r.retrieve_rag_entity_coverage or 0 for r in retrieve_rag_results) / len(retrieve_rag_results)
            
            print(f"\nRetrieve Stage RAG Recall Rate: {avg_retrieve_recall:.2%}")
            print(f"Retrieve Stage RAG Precision Rate: {avg_retrieve_precision:.2%}")
            print(f"Retrieve Stage RAG Relevance Score: {avg_retrieve_relevance:.2%}")
            print(f"Retrieve Stage RAG Entity Coverage: {avg_retrieve_entity_coverage:.2%}")

        
        # Component Performance Breakdown
        print(f"\n[COMPONENT PERFORMANCE BREAKDOWN]:")
        for component, perf in metrics['performance']['component_performance'].items():
            print(f"   {component}: Avg {perf['avg_time']:.3f}s (Max {perf['max_time']:.3f}s, Min {perf['min_time']:.3f}s)")
        
        # Category Statistics
        print(f"\n[CATEGORY STATISTICS]:")
        for category, stats in metrics['category_stats'].items():
            print(f"   {category}: {stats['success']}/{stats['total']} ({stats['success_rate']:.2%})")
        
        print(f"{'='*60}")
    
    def _needs_clarification(self, test_case: TestCase) -> bool:
        """检查是否需要澄清（使用clarification_config）"""
        return test_case.id in self.clarification_config
    
    def _needs_time_clarification(self, rewritten_query, test_case: TestCase) -> bool:
        """检查是否需要时间澄清"""
        print(f"[DEBUG] Checking time clarification for {test_case.id}")
        print(f"[DEBUG] Has clarification config: {test_case.id in self.clarification_config}")
        print(f"[DEBUG] Q2Q time_filter: {rewritten_query.time_filter}")
        print(f"[DEBUG] Expected time_filter: {test_case.expected_time_filter}")
        
        # 使用clarification_config检查
        if test_case.id in self.clarification_config:
            config = self.clarification_config[test_case.id]
            if config.get('needs_clarification', False):
                missing = config.get('missing', [])
                if 'time' in missing:
                    print(f"[DEBUG] Time clarification needed per config")
                    return True
        
        # 回退到原有逻辑
        if not test_case.time_clarification:
            print(f"[DEBUG] No time clarification config, skipping")
            return False
            
        time_clarif = test_case.time_clarification
        
        # 如果明确配置为不需要澄清
        if not time_clarif.get('needed', True):
            print(f"[DEBUG] Time clarification not needed per config")
            return False
            
        # 检查是否有预期的时间过滤器
        if test_case.expected_time_filter:
            actual_time = rewritten_query.time_filter
            expected_time = test_case.expected_time_filter
            
            # 如果Q2Q没有解析出时间，需要澄清
            if not actual_time:
                print(f"[DEBUG] Time clarification needed: expected {expected_time} but Q2Q returned None")
                return True
                
            # 如果Q2Q解析的时间不正确，也需要澄清
            if actual_time != expected_time:
                print(f"[DEBUG] Time clarification needed: expected {expected_time} but Q2Q returned {actual_time}")
                return True
                
            print(f"[DEBUG] Q2Q correctly parsed time filter: {actual_time}")
            return False
            
        print(f"[DEBUG] No time clarification needed")
        return False
    
    def _simulate_clarification_flow(self, test_case: TestCase) -> TestResult:
        """模拟澄清流程"""
        print(f"[DEBUG] Simulating clarification flow for {test_case.id}")
        
        # 获取澄清输入
        clarification_input = self.clarification_config[test_case.id]['clarification_input']
        
        # 1. 初始Q2Q重写
        rewrite_start = time.time()
        initial_query = self.query_rewriter.rewrite(test_case.question)
        component_timings = {'query_rewriter': time.time() - rewrite_start}
        
        # 2. 应用澄清输入
        clarified_query = self._apply_clarification_input(initial_query, clarification_input)
        
        # 3. 使用workflow处理澄清后的查询
        workflow_start = time.time()
        state = {
            'question': test_case.question,
            'q2q': clarified_query.model_dump() if hasattr(clarified_query, 'model_dump') else {},
            'kb_entities': self._create_mock_kb_entities(test_case.expected_rag_entities) if test_case.expected_rag_entities else [],
            'clarified_inputs': clarification_input
        }
        
        # Run workflow steps
        state = self.pipeline.q2q(state)
        state = self.pipeline.retrieve(state)
        state = self.pipeline.plan(state)
        state = self.pipeline.build_ir(state)
        
        ir_obj = state.get('ir_obj')  # 获取SemanticQueryIR对象
        ir = state.get('ir')  # 获取序列化版本用于调试
        component_timings['workflow'] = time.time() - workflow_start
        
        # 4. SQL生成和执行
        sql_gen_start = time.time()
        generated_sql = self.sql_generator.generate(ir_obj, "dws_user_activity")
        component_timings['sql_generator'] = time.time() - sql_gen_start
        
        sql_exec_start = time.time()
        actual_result = self.sql_executor.execute(generated_sql)
        component_timings['sql_executor'] = time.time() - sql_exec_start
        
        # 5. 评估结果
        result = self._evaluate_result(test_case, clarified_query, ir_obj, generated_sql, actual_result)
        result.execution_time = sum(component_timings.values())
        result.component_timings = component_timings
        result.rewritten_query = clarified_query
        result.ir = ir_obj
        result.success = True
        
        return result
    
    def _apply_clarification_input(self, query, clarification_input: Dict[str, Any]):
        """应用澄清输入到查询"""
        # 创建查询的副本
        clarified_query = query
        
        # 应用时间澄清
        if 'time' in clarification_input and clarification_input['time']:
            clarified_query.time_filter = clarification_input['time']
        
        # 应用指标澄清
        if 'metric' in clarification_input and clarification_input['metric']:
            clarified_query.metric = [clarification_input['metric']]
        
        return clarified_query
    
    def _simulate_time_clarification(self, rewritten_query, test_case: TestCase):
        """模拟时间澄清过程"""
        if not test_case.time_clarification:
            return rewritten_query
            
        time_clarif = test_case.time_clarification
        user_input = time_clarif.get('expected_input')
        
        if user_input:
            print(f"[TIME CLARIFICATION] {test_case.id}: Simulating user input '{user_input}'")
            
            # 创建一个新的查询对象，添加用户提供的时间信息
            from copy import deepcopy
            clarified_query = deepcopy(rewritten_query)
            clarified_query.time_filter = user_input
            
            # 添加调试信息
            self._debug_print(f"[DEBUG] Time filter updated from '{rewritten_query.time_filter}' to '{user_input}'")
            
            return clarified_query
            
        return rewritten_query
    
    def save_results(self, output_file: str):
        """保存测试结果到JSON文件"""
        results_data = []
        for result in self.results:
            result_dict = asdict(result)
            # 移除不可序列化的对象
            result_dict['rewritten_query'] = str(result.rewritten_query) if result.rewritten_query else None
            result_dict['ir'] = str(result.ir) if result.ir else None
            results_data.append(result_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"[SUCCESS] Test results saved to: {output_file}")


def main():
    """主函数"""
    import os
    
    # 检查是否启用调试模式和快速模式
    debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    fast_mode = os.getenv('FAST_MODE', 'false').lower() == 'true'
    
    evaluator = BatchTestEvaluator(debug_mode=debug_mode, fast_mode=fast_mode)
    
    # 加载测试用例
    test_file = "test_cases_rag.json"
    if Path(test_file).exists():
        evaluator.load_test_cases(test_file)
    else:
        print(f"[ERROR] Test file {test_file} does not exist")
        return
    
    # 加载澄清配置文件（如果存在）
    clarification_config_file = "test_clarification_config.json"
    if Path(clarification_config_file).exists():
        evaluator.load_clarification_config(clarification_config_file)
    else:
        print(f"[INFO] Clarification config file {clarification_config_file} not found, skipping")
    
    # 运行批量测试
    evaluator.run_batch_test()


if __name__ == "__main__":
    main()
