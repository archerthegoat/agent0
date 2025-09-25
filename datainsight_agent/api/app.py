"""
FastAPI应用

提供RESTful API接口
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any
import uvicorn

from .models import QueryRequest, QueryResponse, HealthResponse, ErrorResponse
from .service import APIService
from datainsight_agent.config.settings import load_settings
from datainsight_agent.common.logging import get_logger

logger = get_logger("api_app")

# 全局API服务实例
api_service: APIService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global api_service
    # 启动时初始化
    logger.info("启动DataInsight Agent API服务")
    api_service = APIService()
    yield
    # 关闭时清理
    logger.info("关闭DataInsight Agent API服务")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    settings = load_settings()
    
    app = FastAPI(
        title=settings.project_info["name"],
        description=settings.project_info["description"],
        version=settings.project_info["version"],
        lifespan=lifespan
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


@app.get("/", response_model=Dict[str, str])
async def root():
    """根路径"""
    return {
        "message": "DataInsight Agent API",
        "version": load_settings().project_info["version"],
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    global api_service
    if not api_service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    health_data = await api_service.get_health_status()
    return HealthResponse(**health_data)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """执行查询"""
    global api_service
    if not api_service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    try:
        response = await api_service.process_query(request)
        return response
    except Exception as e:
        logger.error(f"API查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/simple")
async def simple_query(question: str, user_id: str = "default_user"):
    """简单查询接口（GET方式）"""
    global api_service
    if not api_service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    try:
        request = QueryRequest(
            question=question,
            user_id=user_id,
            validate=True,
            live=False,
            execute=True
        )
        response = await api_service.process_query(request)
        return response
    except Exception as e:
        logger.error(f"简单查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message="服务器内部错误",
            details={"exception": str(exc)}
        ).dict()
    )


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "datainsight_agent.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
