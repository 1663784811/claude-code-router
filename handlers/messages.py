from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI
import traceback

from handlers.util.OpenaiToAnthropic import openai_stream_to_anthropic, openai_to_anthropic
from handlers.util.AnthropicToOpenai import anthropic_to_openai_request
from handlers.util.ErrorMap import map_openai_exception

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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",
    max_retries=2,      # 429 时会自动指数退避重试 2 次
    timeout=120.0,
)


async def handle_messages(request: Request):
    print('--------------- 处理： /v1/messages ---------------')
    anthropic_body = await request.json()

    openai_body = anthropic_to_openai_request(anthropic_body)
    model = openai_body["model"]
    messages = openai_body["messages"]

    extra_kwargs = {}
    for k in ("max_tokens", "temperature", "top_p", "stop", "tools", "tool_choice", "user"):
        if k in openai_body and openai_body[k] is not None:
            extra_kwargs[k] = openai_body[k]

    # ★★★ 关键：把 create 调用放进 try 里 ★★★
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
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
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
        print("handle_messages 上游异常:", repr(e))
        traceback.print_exc()
        return map_openai_exception(e)