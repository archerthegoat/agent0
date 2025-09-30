from __future__ import annotations

from typing import Callable

from fastapi import Request


class APIKeyAuthMiddleware:
    """Simple API-key auth via header X-API-Key. Optional; no-op if not set.

    Set expected key via env (e.g., API_KEY). If not configured, middleware
    allows all requests.
    """

    def __init__(self, app, header_name: str = "X-API-Key", env_var: str = "API_KEY") -> None:
        self.app = app
        self.header_name = header_name
        self.env_var = env_var

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # lazy import to avoid early settings load
        import os
        expected = os.getenv(self.env_var, "")
        if not expected:
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        got = request.headers.get(self.header_name, "")
        if got and got == expected:
            await self.app(scope, receive, send)
            return
        from starlette.responses import JSONResponse
        res = JSONResponse(status_code=401, content={"error": "unauthorized", "message": "invalid api key"})
        await res(scope, receive, send)




