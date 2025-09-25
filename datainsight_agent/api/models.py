"""
API数据模型

定义API请求和响应的数据结构
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datainsight_agent.models.ir import SemanticQueryIR


class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., description="用户问题", example="用户活跃度分析")
    user_id: Optional[str] = Field("default_user", description="用户ID")
    validate_sql: bool = Field(True, description="是否验证SQL")
    live: bool = Field(False, description="是否实时执行")
    execute: bool = Field(True, description="是否执行SQL")
    metric_override: Optional[str] = Field(None, description="指标覆盖")
    time_filter_override: Optional[str] = Field(None, description="时间过滤覆盖")


class QueryResponse(BaseModel):
    """查询响应模型"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
    timing: Optional[Dict[str, float]] = Field(None, description="执行时间")


class PlanResponse(BaseModel):
    """计划响应模型"""
    plan: str = Field(..., description="执行计划")
    ir: Optional[SemanticQueryIR] = Field(None, description="中间表示")
    sql: Optional[str] = Field(None, description="生成的SQL")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="查询结果")
    attribution_report: Optional[str] = Field(None, description="归因分析报告")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本信息")
    timestamp: str = Field(..., description="时间戳")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
