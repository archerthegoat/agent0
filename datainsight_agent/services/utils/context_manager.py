"""
分阶段Context管理系统
根据不同的处理阶段动态提供相应的Context，避免不必要的token浪费
"""

from typing import Dict, Any, Optional
import re


class StageAwareContextManager:
    """分阶段Context管理器"""
    
    def __init__(self):
        self._context_cache = {}
        self._stage_contexts = {
            'q2q': self._build_q2q_context,
            'ir_build': self._build_ir_context, 
            'rag_retrieve': self._build_rag_context,
            'sql_generate': self._build_sql_context
        }
    
    def get_context(self, stage: str, question: str, **kwargs) -> str:
        """根据阶段获取相应的Context"""
        if stage not in self._stage_contexts:
            return ""
        
        # 检查缓存
        cache_key = f"{stage}:{hash(question)}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
        
        # 构建阶段特定Context
        context = self._stage_contexts[stage](question, **kwargs)
        
        # 缓存结果
        self._context_cache[cache_key] = context
        return context
    
    def _build_q2q_context(self, question: str, kb_ctx: str = "") -> str:
        """Q2Q阶段Context：增强时间解析指导 + KB上下文"""
        # 检测查询类型
        query_type = self._detect_query_type(question)
        
        # 增强的时间解析指导
        base_guidance = """Rules:
- GROUP BY: trends need it, single queries don't
- TIME FORMATS:
  * Single: "2025-08" (YYYY-MM)
  * Range: "2025-08,2025-09" (start,end)
  * Quarter: "2025-Q3" → "2025-07,2025-09"
  * Year: "2025" → "2025-01,2025-12"
- CONFIDENCE: clear≥0.7, relative≥0.6, unclear<0.4"""
        
        # 按需添加详细时间指导
        time_guidance = ""
        if query_type['has_relative_time']:
            time_guidance = """
RELATIVE TIME MAPPING:
- 上月/last month → "2025-08"
- 今年/this year → "2025-01,2025-12"  
- 去年/last year → "2024-01,2024-12"
- 最近2个月 → "2025-08,2025-09"
- 本月/this month → "2025-09" """
        
        if query_type['has_quarter']:
            time_guidance += """
QUARTER MAPPING:
- 2025年第3季度 → "2025-07,2025-09"
- Q3 → "2025-07,2025-09"
- 第三季度 → "2025-07,2025-09"
- Q1 → "2025-01,2025-03"
- Q2 → "2025-04,2025-06"  
- Q4 → "2025-10,2025-12" """
        
        if query_type['has_trend']:
            time_guidance += "\nTREND: Add GROUP BY month"
        
        # 压缩KB上下文
        compressed_kb = self._compress_kb_context(kb_ctx)
        
        return f"{compressed_kb}\n{base_guidance}{time_guidance}"
    
    def _build_ir_context(self, question: str, **kwargs) -> str:
        """IR构建阶段Context：表结构信息，不需要解析指导"""
        # 只提供表结构信息，不包含解析指导
        table_info = self._get_table_structure()
        return f"Tables: {table_info}"
    
    def _build_rag_context(self, question: str, **kwargs) -> str:
        """二段RAG阶段Context：语义检索，不需要Q2Q指导"""
        # 只提供语义检索相关的上下文
        semantic_context = self._get_semantic_context(question)
        return semantic_context
    
    def _build_sql_context(self, question: str, **kwargs) -> str:
        """SQL生成阶段Context：SQL模板，不需要解析指导"""
        # 只提供SQL生成相关的模板
        sql_templates = self._get_sql_templates()
        return f"SQL Templates: {sql_templates}"
    
    def _detect_query_type(self, question: str) -> Dict[str, bool]:
        """检测查询类型"""
        # 直接使用原始问题进行检测，避免lower()导致的Unicode问题
        return {
            'has_time': any(word in question for word in ['年', '月', '日', '最近', '今年', '去年']),
            'has_relative_time': any(word in question for word in ['最近', '上月', '今年', '去年', '本月']),
            'has_quarter': any(word in question for word in [
                '季度', '第', 'q', 'Q1', 'Q2', 'Q3', 'Q4', 
                '第一季度', '第二季度', '第三季度', '第四季度',
                '一季度', '二季度', '三季度', '四季度'
            ]),
            'has_trend': any(word in question for word in ['趋势', '各月', '按月', 'trend']),
            'has_grouping': any(word in question for word in ['按', '分组', 'group by']),
            'is_simple': len(question.split()) <= 5 and not any(word in question for word in ['年', '月', '到', '按'])
        }
    
    def _compress_kb_context(self, kb_ctx: str) -> str:
        """压缩KB上下文，保留关键信息"""
        if not kb_ctx:
            return ""
        
        lines = kb_ctx.split('\n')
        compressed = []
        
        # 只保留前6行关键信息
        for line in lines[:6]:
            if '->' in line or ':' in line:  # 保留映射和定义
                compressed.append(line)
        
        return '\n'.join(compressed)
    
    def _get_table_structure(self) -> str:
        """获取表结构信息"""
        return "dws_user_activity(month, user_id)"
    
    def _get_semantic_context(self, question: str) -> str:
        """获取语义检索上下文"""
        return "Semantic search context for metrics and dimensions"
    
    def _get_sql_templates(self) -> str:
        """获取SQL模板"""
        return "SELECT COUNT(user_id) AS metric FROM table WHERE month = 'YYYY-MM'"
    
    def clear_cache(self):
        """清理缓存"""
        self._context_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'cache_size': len(self._context_cache),
            'cached_stages': list(set(key.split(':')[0] for key in self._context_cache.keys()))
        }
