from __future__ import annotations

import time
from typing import Callable

from fastapi import Request

from datainsight_agent.common.logging import get_logger


class RequestLoggingMiddleware:
    """Structured request logging middleware."""

    def __init__(self, app) -> None:
        self.app = app
        self.logger = get_logger("api_requests")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        start = time.time()
        try:
            await self.app(scope, receive, send)
        finally:
            dur = time.time() - start
            self.logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                duration_ms=int(dur * 1000),
            )




