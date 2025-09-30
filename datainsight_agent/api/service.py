"""
API服务层

处理API请求的业务逻辑
"""

from typing import Dict, Any, Optional
from datainsight_agent.orchestrator.li.pipeline import LIPipeline
from datainsight_agent.components.query_rewriter import QueryRewriter
from datainsight_agent.components.time_parser import TimeParser
from datainsight_agent.components.sql_generator import SQLGeneratorComponent, SQLExecutorComponent
from datainsight_agent.config.settings import load_settings
from datainsight_agent.common.logging import get_logger
from .models import QueryRequest, QueryResponse, PlanResponse

logger = get_logger("api_service")


class APIService:
    """API服务类"""
    
    def __init__(self):
        self.settings = load_settings()
        self.pipeline = LIPipeline()
        self.logger = get_logger("api_service")
    
    async def process_query(self, request: QueryRequest) -> QueryResponse:
        """处理查询请求"""
        try:
            self.logger.info(f"处理查询请求: {request.question}")
            
            # 构建pipeline状态
            state = {
                "question": request.question,
                "user_id": request.user_id,
                "validate": request.validate_sql,
                "live": request.live,
                "execute": request.execute,
            }
            
            # 如果有覆盖参数，添加到状态中
            if request.metric_override:
                state["metric_override"] = request.metric_override
            if request.time_filter_override:
                state["time_filter_override"] = request.time_filter_override
            
            # 执行原有 pipeline（仅保留原链路）
            result = {}
            for values in self.pipeline.stream(state, stream_mode="values"):
                if isinstance(values, dict):
                    result.update(values)
            
            # 构建响应数据
            response_data = {
                "plan": result.get("plan", "unknown"),
                "ir": result.get("ir"),
                "sql": result.get("sql"),
                "results": result.get("results"),
                "attribution_report": result.get("attribution_report"),
                "timing": result.get("timing", {})
            }
            
            return QueryResponse(
                success=True,
                message="查询处理成功",
                data=response_data,
                timing=result.get("timing", {})
            )
            
        except Exception as e:
            self.logger.error(f"查询处理失败: {str(e)}")
            return QueryResponse(
                success=False,
                message="查询处理失败",
                error=str(e)
            )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        from datetime import datetime
        try:
            # 简单的健康检查
            return {
                "status": "healthy",
                "version": self.settings.project_info["version"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
