"""
统一的错误映射：把上游 OpenAI SDK 异常转换成 Anthropic 风格的错误响应。

Anthropic 的错误体格式：
    {"type": "error", "error": {"type": "<err_type>", "message": "<message>"}}
"""

from fastapi.responses import JSONResponse
from openai import (
    APIStatusError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError,
)


def anthropic_error(status_code: int, err_type: str, message: str) -> JSONResponse:
    """构造一个 Anthropic 格式的错误响应"""
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": err_type, "message": message}},
    )


def map_openai_exception(e: Exception) -> JSONResponse:
    """把上游 OpenAI SDK 异常映射成 Anthropic 格式的错误响应"""
    if isinstance(e, RateLimitError):
        return anthropic_error(429, "rate_limit_error", f"上游限流(rpm exhausted): {e}")
    if isinstance(e, AuthenticationError):
        return anthropic_error(401, "authentication_error", f"上游鉴权失败: {e}")
    if isinstance(e, APITimeoutError):
        return anthropic_error(504, "timeout_error", f"上游超时: {e}")
    if isinstance(e, APIConnectionError):
        return anthropic_error(502, "api_error", f"无法连接上游: {e}")
    if isinstance(e, APIStatusError):
        return anthropic_error(e.status_code or 500, "api_error", f"上游错误: {e}")
    return anthropic_error(500, "api_error", f"代理异常: {e}")
