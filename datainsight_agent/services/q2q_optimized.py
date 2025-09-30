"""
OPTIMIZED: Enhanced Q2Q implementation with intelligent context management.

This module combines the best features from both q2q.py and q2q_with_context_manager.py:
1. Dynamic stage-aware context management
2. Enhanced time parsing with focused system prompts
3. Optimized token usage through selective prompting
4. Robust fallback mechanisms
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from datainsight_agent.services.llm import QwenClient
from datainsight_agent.config.settings import load_settings
from datainsight_agent.services.kb_vector_index import KBVectorRetriever


class Q2QRewrite(BaseModel):
    rewritten_question: Optional[str] = None
    metric: List[str] = []
    group_by: List[str] = []
    time_filter: Optional[str] = None
    concepts: List[str] = []
    clarify: bool = False
    ask: Optional[str] = None
    # RAG相关字段
    rag_context: Optional[str] = None
    rag_fragments: Optional[List[Dict[str, Any]]] = None


class OptimizedQ2QRewriter:
    """Optimized LLM+RAG Query-to-Query rewriter with intelligent context management.

    Key optimizations:
    1. Stage-aware context management (from q2q_with_context_manager.py)
    2. Enhanced time parsing system prompts (from q2q.py)
    3. Selective prompting based on query type
    4. Progressive fallback mechanisms
    """

    def __init__(self, metadata_dir: str | None = None) -> None:
        from datainsight_agent.config.settings import load_settings
        s = load_settings()
        self._metadata_dir = metadata_dir or s.metadata_dir
        
        # 延迟初始化组件
        self._kb_retriever = None
        self._kb_retriever_initialized = False
        self._client = None
        
        # 智能Context管理器
        from datainsight_agent.services.context_manager import StageAwareContextManager
        self._context_manager = StageAwareContextManager()
        
        # 查询类型检测器缓存
        self._query_type_cache = {}

    def _get_kb_retriever(self):
        """懒加载KB向量检索器"""
        if not self._kb_retriever_initialized:
            try:
                if not hasattr(OptimizedQ2QRewriter, '_shared_kb_retriever'):
                    OptimizedQ2QRewriter._shared_kb_retriever = KBVectorRetriever("kb_vector_index")
                self._kb_retriever = OptimizedQ2QRewriter._shared_kb_retriever
            except Exception:
                self._kb_retriever = None
            self._kb_retriever_initialized = True
        return self._kb_retriever

    def _get_client(self):
        """懒加载LLM客户端"""
        if not self._client:
            from datainsight_agent.config.settings import load_settings
            settings = load_settings()
            self._client = QwenClient(settings)
        return self._client

    def _detect_query_type(self, question: str) -> Dict[str, bool]:
        """智能查询类型检测，缓存结果"""
        cache_key = hash(question)
        if cache_key in self._query_type_cache:
            return self._query_type_cache[cache_key]
        
        query_type = {
            'has_time': any(word in question for word in ['年', '月', '日', '最近', '今年', '去年']),
            'has_relative_time': any(word in question for word in ['最近', '上月', '今年', '去年', '本月', '今年']),
            'has_quarter': any(word in question for word in [
                '季度', '第', 'q', 'Q1', 'Q2', 'Q3', 'Q4', 
                '第一季度', '第二季度', '第三季度', '第四季度',
                '一季度', '二季度', '三季度', '四季度'
            ]),
            'has_trend': any(word in question for word in ['趋势', '各月', '按月', 'trend', '曲线']),
            'has_grouping': any(word in question for word in ['按', '分组', 'group by']),
            'has_range': any(word in question for word in ['到', '至', '-', '～']),
            'is_simple': len(question.split()) <= 6 and not any(word in question for word in ['年', '月', '到', '按', '趋势'])
        }
        
        self._query_type_cache[cache_key] = query_type
        return query_type

    def _build_system_prompt(self, query_type: Dict[str, bool]) -> str:
        """根据查询类型动态构建系统提示词"""
        
        # 基础时间解析规则
        base_rules = """Extract time information from Chinese queries following exact patterns:

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
  * "按渠道统计MAU" → type="single", value="2025-08" (current month)
  * "按地区统计DAU" → type="single", value="2025-08" (current month)  
  * "设备分析" → type="single", value="2025-08" (current month)
  * "平台对比" → type="single", value="2025-08" (current month)
  * Any statistical query without time → type="single", value="2025-08"

IMPORTANT: Always provide a time_filter, never leave it as "none" for statistical queries!
"""

        # 添加默认时间推断规则
        default_time_inference = """

DEFAULT TIME INFERENCE - Apply when no explicit time found:
- Statistical queries need default time scope
- Use current month "2025-08" as default
- Never return time_filter as "none" for MAU/DAU/UV/PV queries
"""

        # 添加GROUP BY字段映射规则
        group_by_mapping = """

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

IMPORTANT: Use exact English field names, NOT Chinese or mixed names!
"""

        # 添加指标标准化指导
        metric_standardization = """

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

CRITICAL RULE: Always prioritize RAG context standard names over original Chinese terms!
"""

        # 按需添加特定指导
        focused_rules = ""
        
        if query_type['has_quarter']:
            focused_rules += """
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
- Only add group_by=["quarter"] if explicitly asking for quarter comparison
"""

        if query_type['has_relative_time']:
            focused_rules += """
RELATIVE TIME MAPPING:
- 最近2个月 = "last_2_months" (format as range)
- 今年 = "2025-01,2025-12"
- 去年 = "2024-01,2024-12" 
- 本月 = "2025-09"
- 上月 = "2025-08"
"""

        if query_type['has_trend']:
            focused_rules += """
TREND ANALYSIS: 
- For monthly trends: Add group_by=["month"] 
- For quarterly trends: Do NOT add group_by=["month"] - use aggregation instead
- For yearly trends: Add group_by=["year"]
- For quarter analysis queries: Use aggregation without grouping
"""

        return f"{base_rules}{default_time_inference}{group_by_mapping}{metric_standardization}{focused_rules}\nAlways set confidence >= 0.8 for clear expressions."

    def _build_minimal_json_schema(self, query_type: Dict[str, bool]) -> Dict[str, Any]:
        """根据查询类型优化JSON Schema，减少不必要的字段"""
        
        base_schema = {
            "type": "object",
            "properties": {
                "metric": {"type": "array", "items": {"type": "string"}},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "time_filter": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["single", "range", "quarter", "relative", "year", "none"]},
                        "value": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                    },
                    "required": ["type", "value", "confidence"]
                },
                "concepts": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["metric", "group_by", "time_filter", "concepts"],
            "additionalProperties": False,
        }

        # 如果不是时间查询，简化schema
        if not query_type['has_time']:
            base_schema["properties"]["time_filter"]["properties"]["type"]["enum"] = ["none"]

        return base_schema

    def _get_rag_content(self, question: str) -> tuple[str, str]:
        """获取RAG内容：kb_context + rag_fragments"""
        kb_retriever = self._get_kb_retriever()
        if not kb_retriever:
            return "", ""

        try:
            # 获取向量检索结果
            fragments = kb_retriever.search_topics_and_metrics(question, top_k=5)
            rag_context = ""
            rag_fragments = []

            if fragments:
                # 构建上下文
                context_parts = []
                for fragment in fragments[:3]:  # 只取前3个，节省token
                    if isinstance(fragment, dict):
                        metadata = fragment.get('metadata', {})
                        if metadata:
                            entity_type = metadata.get('entity_type', 'unknown')
                            entity_name = metadata.get('entity_name', 'unknown')
                            
                            # 对于指标实体，添加标准别名信息
                            if entity_type == 'metric':
                                canonical_name = metadata.get('canonical_name', '')
                                aliases = metadata.get('aliases', [])
                                aggregation = metadata.get('aggregation', {})
                                
                                # 构建详细的指标信息
                                metric_info = f"{entity_name}"
                                if canonical_name:
                                    metric_info += f" (标准名称: {canonical_name})"
                                if aliases:
                                    # 只显示英文标准别名
                                    english_aliases = [alias for alias in aliases if alias.isupper() and len(alias) <= 4]
                                    if english_aliases:
                                        metric_info += f" [标准别名: {', '.join(english_aliases)}]"
                                if aggregation:
                                    alias = aggregation.get('alias', '')
                                    if alias:
                                        metric_info += f" [SQL别名: {alias}]"
                                
                                context_parts.append(f"{entity_type}:{metric_info}")
                            else:
                                context_parts.append(f"{entity_type}:{entity_name}")
                        rag_fragments.append(fragment)

                rag_context = "; ".join(context_parts)
            
            return rag_context, rag_fragments
        except Exception:
            return "", []

    def rewrite(self, question: str) -> Q2QRewrite:
        """主重写方法：结合Context管理和增强解析"""
        
        # 1. 智能查询分析
        query_type = self._detect_query_type(question)
        
        # 2. 按需获取RAG内容
        kb_ctx, rag_fragments = self._get_rag_content(question)
        
        # 3. 动态Context构建
        context = self._context_manager.get_context(
            stage='q2q',
            question=question,
            kb_ctx=kb_ctx
        )
        
        # 4. 构建优化的提示
        user_prompt = f"{context}\n{question}"
        
        # 5. 动态系统提示词和Schema
        system_prompt = self._build_system_prompt(query_type)
        json_schema = self._build_minimal_json_schema(query_type)
        
        # 6. LLM调用
        client = self._get_client()
        obj = {}
        
        try:
            obj = client.tool_call(
                system=system_prompt,
                user=user_prompt,
                tool_name="q2q_rewrite",
                json_schema=json_schema,
            )
        except Exception:
            # 渐进式回退处理
            obj = self._fallback_parse(user_prompt, json_schema)

        # 7. 结果标准化
        return self._normalize_result(obj, question, kb_ctx, rag_fragments)

    def _fallback_parse(self, prompt: str, schema: dict) -> dict:
        """渐进式回退解析"""
        client = self._get_client()
        
        # 回退1：添加格式指导的JSON解析
        enhanced_prompt = f"""{prompt}

Return JSON format:
{{
  "metric": ["mau", "dau"], 
  "group_by": ["month"],
  "time_filter": {{"type": "single", "value": "2025-08", "confidence": 0.9}},
  "concepts": ["user", "activity"]
}}"""
        
        try:
            obj = client.tool_call(
                system="Return valid JSON only.",
                user=enhanced_prompt,
                tool_name="q2q_rewrite", 
                json_schema=schema,
            )
            if isinstance(obj, dict) and obj:
                return obj
        except Exception:
            pass
        
        # 回退2：纯文本解析
        try:
            text_response = client.generate(prompt + "\n\nPlease return JSON format.")
            return self._extract_json_from_text(text_response)
        except Exception:
            return {}

    def _extract_json_from_text(self, text: str) -> dict:
        """从文本中提取JSON"""
        import json
        import re
        
        # 查找JSON块
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _normalize_result(self, obj: dict, question: str, kb_ctx: str, rag_fragments: list) -> Q2QRewrite:
        """标准化结果"""
        if not isinstance(obj, dict):
            obj = {}

        # 获取各项结果
        metrics = obj.get('metric', [])
        group_by = obj.get('group_by', [])
        time_filter_obj = obj.get('time_filter', {})
        concepts = obj.get('concepts', [])

        # 标准化时间过滤器
        time_filter = self._normalize_time_filter(time_filter_obj, question)

        # 构建澄清逻辑
        clarify = self._should_clarify(metrics, time_filter, concepts)
        ask_message = self._get_clarification_message(metrics, time_filter) if clarify else None

        return Q2QRewrite(
            rewritten_question=question,
            metric=metrics or [],
            group_by=group_by or [],
            time_filter=time_filter,
            concepts=concepts or [],
            clarify=clarify,
            ask=ask_message,
            rag_context=kb_ctx,
            rag_fragments=rag_fragments
        )

    def _normalize_time_filter(self, time_filter_obj: dict, question: str) -> str:
        """标准化时间过滤器"""
        if not time_filter_obj or time_filter_obj.get('type') == 'none':
            return None
        
        time_type = time_filter_obj.get('type')
        value = time_filter_obj.get('value', '')
        confidence = time_filter_obj.get('confidence', 0.0)
        
        # 降低置信度阈值
        if confidence < 0.3:
            return None
        
        # 智能标准化
        if time_type == 'single':
            return self._normalize_single_time_value(value)
        elif time_type == 'range':
            return self._normalize_range_time_value(value)
        elif time_type == 'quarter':
            return self._normalize_quarter_time_value(value)
        elif time_type == 'relative':
            return self._normalize_relative_time_value(value, question)
        elif time_type == 'year':
            return self._normalize_year_time_value(value)
        
        return value

    def _normalize_single_time_value(self, value: str) -> str:
        """标准化单月时间"""
        import re
        
        # YYYY年MM月格式
        match = re.search(r'(\d{4})年(\d{1,2})月', value)
        if match:
            year, month = match.groups()
            return f"{year}-{int(month):02d}"
        
        return value

    def _normalize_range_time_value(self, value: str) -> str:
        """标准化时间范围"""
        import re
        
        # 处理 "2025年8月到2025年9月" 格式
        match = re.search(r'(\d{4})年(\d{1,2})月到(\d{4})年(\d{1,2})月', value)
        if match:
            start_year, start_month, end_year, end_month = match.groups()
            return f"{start_year}-{int(start_month):02d},{end_year}-{int(end_month):02d}"
        
        return value

    def _normalize_quarter_time_value(self, value: str) -> str:
        """标准化季度时间"""
        import re
        
        # 支持多种季度格式:
        # 1. "2025年第3季度" → 2025-07,2025-09
        # 2. "2025-Q3" → 2025-07,2025-09  
        # 3. "2025年Q3" → 2025-07,2025-09
        
        # 中文"第...季度"格式
        match = re.search(r'(\d{4})年第(\d)季度', value)
        if match:
            year, quarter = match.groups()
            q = int(quarter)
            start_month = (q - 1) * 3 + 1
            end_month = q * 3
            return f"{year}-{start_month:02d},{year}-{end_month:02d}"
        
        # English Q format "2025-Q3" or "2025Q3"
        match = re.search(r'(\d{4})-?Q(\d)', value)
        if match:
            year, quarter = match.groups()
            q = int(quarter)
            start_month = (q - 1) * 3 + 1
            end_month = q * 3
            return f"{year}-{start_month:02d},{year}-{end_month:02d}"
        
        return value

    def _normalize_relative_time_value(self, value: str, question: str) -> str:
        """标准化相对时间"""
        import datetime as dt
        
        base_date = dt.date(2025, 9, 28)  # 模拟当前日期
        
        if '最近' in question and '个月' in question:
            import re
            months_match = re.search(r'最近(\d+)个月', question)
            if months_match:
                n = int(months_match.group(1))
                if base_date.month <= n:
                    start_year = base_date.year - 1
                    start_month = 12 - (n - base_date.month)
                else:
                    start_year = base_date.year
                    start_month = base_date.month - n + 1
                return f"{start_year}-{start_month:02d},{base_date.year}-{base_date.month:02d}"
        
        if '今年' in question:
            return f"{base_date.year}-01,{base_date.year}-12"
        
        if '去年' in question:
            return f"{base_date.year-1}-01,{base_date.year-1}-12"
        
        if '上月' in question:
            prev_month = base_date.month - 1 if base_date.month > 1 else 12
            prev_year = base_date.year if base_date.month > 1 else base_date.year - 1
            return f"{prev_year}-{prev_month:02d}"
        
        return value

    def _normalize_year_time_value(self, value: str) -> str:
        """标准化年份时间"""
        import re
        
        if match := re.search(r'(\d{4})', value):
            year = match.group(1)
            return f"{year}-01,{year}-12"
        
        return value

    def _should_clarify(self, metrics: list, time_filter: str, concepts: list) -> bool:
        """判断是否需要澄清"""
        # 度量澄清
        if not metrics:
            return True
        
        # 检查度量注册表
        from datainsight_agent.services.metric_registry import MetricRegistry
        registry = MetricRegistry()
        
        # 验证度量是否在注册表中
        invalid_metrics = []
        for metric in metrics:
            if not registry.has_metric(metric):
                invalid_metrics.append(metric)
        
        if invalid_metrics:
            return True
        
        return False

    def _get_clarification_message(self, metrics: list, time_filter: str) -> Optional[str]:
        """获取澄清消息"""
        if not metrics:
            return "请指定要分析的指标（如MAU、DAU、UV等）"
        
        # 检查无效度量
        from datainsight_agent.services.metric_registry import MetricRegistry
        registry = MetricRegistry()
        
        invalid_metrics = []
        for metric in metrics:
            if not registry.has_metric(metric):
                invalid_metrics.append(metric)
        
        if invalid_metrics:
            available_metrics = registry.get_all_metric_names()
            return f"指标 {', '.join(invalid_metrics)} 无效。请从以下选项中选择：{', '.join(available_metrics[:10])}"
        
        return None
