# handlers/messages.py
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from openai import (
    AsyncOpenAI,
    APIStatusError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError,
)
import traceback

from handlers.util.OpenaiToAnthropic import openai_stream_to_anthropic, openai_to_anthropic
from handlers.util.AnthropicToOpenai import anthropic_to_openai_request

client = AsyncOpenAI(
    base_url="https://token.sensenova.cn/v1",
    api_key="sk-AkBjsnJiWyZpixYdBjtQW9zAZFyNyq5h",
    max_retries=3,     # ★ SDK 层自动重试（含 429 退避）
    timeout=120.0,
)


def _anthropic_error(status_code: int, err_type: str, message: str) -> JSONResponse:
    """把上游错误包装成 Anthropic 错误格式"""
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": err_type, "message": message}},
    )


def _map_openai_exception(e: Exception) -> JSONResponse:
    """OpenAI 异常 -> Anthropic 错误响应"""
    if isinstance(e, RateLimitError):
        return _anthropic_error(429, "rate_limit_error", f"上游限流: {e}")
    if isinstance(e, AuthenticationError):
        return _anthropic_error(401, "authentication_error", f"上游鉴权失败: {e}")
    if isinstance(e, APITimeoutError):
        return _anthropic_error(504, "timeout_error", f"上游超时: {e}")
    if isinstance(e, APIConnectionError):
        return _anthropic_error(502, "api_error", f"无法连接上游: {e}")
    if isinstance(e, APIStatusError):
        # 上游返回了非 2xx，尽量透传状态码
        return _anthropic_error(
            e.status_code or 500, "api_error", f"上游错误: {e}"
        )
    return _anthropic_error(500, "api_error", f"代理异常: {e}")


async def handle_messages(request: Request):
    print('--------------- 处理： /v1/messages ---------------')
    anthropic_body = await request.json()
    print("Anthropic 请求body \n", anthropic_body)

    openai_body = anthropic_to_openai_request(anthropic_body)
    print("转换后 OpenAI 请求body \n", openai_body)

    model = openai_body["model"]
    messages = openai_body["messages"]

    extra_kwargs = {}
    for k in ("max_tokens", "temperature", "top_p", "stop", "tools", "tool_choice", "user"):
        if k in openai_body and openai_body[k] is not None:
            extra_kwargs[k] = openai_body[k]

    # ★ 不要直接把 stream=True 传给 create；先拿到响应再决定
    try:
        if openai_body.get("stream"):
            print('--------------- 处理流式 /v1/messages ---------------')
            openai_stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **extra_kwargs,
            )
            return StreamingResponse(
                openai_stream_to_anthropic(openai_stream, model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )
        else:
            print("--------------------- 处理单次响应 --------------------------")
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                **extra_kwargs,
            )
            return JSONResponse(openai_to_anthropic(resp, model))
    except Exception as e:
        # ★ 关键：把上游异常转成 Anthropic 错误格式，避免裸 500
        print("handle_messages 上游异常:", repr(e))
        traceback.print_exc()
        return _map_openai_exception(e)