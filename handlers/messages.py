# handlers/messages.py
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI

from handlers.util.OpenaiToAnthropic import openai_stream_to_anthropic, openai_to_anthropic
from handlers.util.AnthropicToOpenai import anthropic_to_openai_request

client = AsyncOpenAI(
    base_url="https://token.sensenova.cn/v1",
    api_key="sk-AkBjsnJiWyZpixYdBjtQW9zAZFyNyq5h",
)


async def handle_messages(request: Request):
    """处理 /v1/messages：Anthropic 格式 -> OpenAI 格式 -> 再转回 Anthropic 格式"""
    print('--------------- 处理： /v1/messages ---------------')
    anthropic_body = await request.json()
    print("Anthropic 请求body \n", anthropic_body)

    # ★ 关键：Anthropic -> OpenAI
    openai_body = anthropic_to_openai_request(anthropic_body)
    print("转换后 OpenAI 请求body \n", openai_body)

    model = openai_body["model"]
    messages = openai_body["messages"]

    # 组装透传给 OpenAI 的可选参数
    extra_kwargs = {}
    for k in ("max_tokens", "temperature", "top_p", "stop", "tools", "tool_choice", "user"):
        if k in openai_body and openai_body[k] is not None:
            extra_kwargs[k] = openai_body[k]

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