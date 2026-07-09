"""
FastAPI 中间件 — Rate Limit + 统一错误处理。

不引入外部依赖。Rate limit 基于内存字典的滑动窗口。
"""

import time
from collections import defaultdict
import os

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# ── 错误码映射 ──

_STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """统一将 HTTPException 转换为结构化错误格式。"""
    code = _STATUS_TO_CODE.get(exc.status_code, "UNKNOWN")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "detail": None,
            }
        },
    )


def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """统一 Pydantic 校验错误格式。"""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "detail": str(exc),
            }
        },
    )


def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器。"""
    expose_detail = os.environ.get("AI_NEWS_DEBUG_ERRORS") == "1"
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "detail": str(exc) if expose_detail else None,
            }
        },
    )


# ── Rate Limit Middleware ──

class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于内存的滑动窗口限流中间件。

    默认: 60 requests / minute per IP。
    不依赖 Redis，适合单机部署。
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"

        # 滑动窗口清理
        now = time.time()
        cutoff = now - self.window_seconds
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if t > cutoff]

        # 检查限流
        remaining = self.max_requests - len(self._buckets[client_ip])
        if remaining <= 0:
            oldest = min(self._buckets[client_ip])
            reset_at = int(oldest + self.window_seconds)
            response = JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Too many requests. Limit: {self.max_requests}/min",
                        "detail": None,
                    }
                },
            )
        else:
            self._buckets[client_ip].append(now)
            response = await call_next(request)

        # 注入限流头
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        if remaining <= 0:
            response.headers["X-RateLimit-Reset"] = str(reset_at)
        else:
            response.headers["X-RateLimit-Reset"] = str(int(now + self.window_seconds))

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """注入基础安全响应头。

    当前前端仍使用内联 CSS/JS 和少量外部图库 CDN，因此 CSP 先采用
    可运行的收敛版本；后续若迁移为外部静态资源，可去掉 unsafe-inline。
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://d3js.org https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", self.CSP)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


# ── Auth 依赖 ──

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """从 JWT token 解析当前用户。无有效 token → 401。"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    from src.api.auth import decode_token, get_user_by_id
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    request.state.user = user
    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict | None:
    """解析 JWT，但不强制要求。无 token → None。"""
    if not credentials:
        return None
    from src.api.auth import decode_token, get_user_by_id
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user = get_user_by_id(int(payload["sub"]))
    if user:
        request.state.user = user
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """要求当前用户为管理员。非 admin → 403。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── 注册入口 ──

def register_error_handlers(app):
    """在 FastAPI app 上注册所有异常处理器。"""
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _generic_exception_handler)
