"""
维度解析器

将维度解析逻辑从_BuildIRComponent中提取出来，提供更清晰的接口。
"""

from typing import Dict, Any, List
from datainsight_agent.config.keyword_mappings import DIMENSION_KEYWORDS


class DimensionParser:
    """维度解析器"""
    
    def parse_dimensions(self, state: Dict[str, Any]) -> List[str]:
        """
        解析维度并返回group_by列表
        
        Args:
            state: 管道状态
            
        Returns:
            维度列名列表
        """
        group_by: List[str] = []

        # 优先级：Q2Q明确给出的 group_by 最为权威；若存在，则严格使用它，不再扩展 KB/关键词
        q2q = state.get("q2q") or {}
        q2q_group_by = q2q.get("group_by", [])
        if isinstance(q2q_group_by, list) and len(q2q_group_by) > 0:
            for gb in q2q_group_by:
                if isinstance(gb, str):
                    gbs = gb.strip()
                    if gbs and gbs not in group_by:
                        group_by.append(gbs)
            return group_by

        # 否则在无 Q2Q 指定时，再从 KB 实体与问题关键词推断
        entities = state.get("kb_entities", []) or []
        for entity in entities:
            try:
                if (getattr(entity, "type", "").lower() == "dimension" and 
                    entity.how and entity.how.data_source and entity.how.data_source.column):
                    col = entity.how.data_source.column
                    if col and col not in group_by:
                        group_by.append(col)
            except Exception:
                continue

        question = str(state.get("question") or "").lower()
        for keyword, column in DIMENSION_KEYWORDS.items():
            if keyword in question and column not in group_by:
                group_by.append(column)

        return group_by


# 全局实例
_parser_instance = None

def parse_dimensions(state: Dict[str, Any]) -> List[str]:
    """解析维度的便捷函数"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = DimensionParser()
    return _parser_instance.parse_dimensions(state)
