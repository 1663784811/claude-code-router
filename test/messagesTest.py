import asyncio
import json

from starlette.requests import Request

from handlers.messages import handle_messages


def make_request(body: dict, headers: dict = None) -> Request:
    """构造一个带 JSON body 的模拟 Request"""
    headers = headers or {}
    body_bytes = json.dumps(body).encode("utf-8")

    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/messages",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in headers.items()
        ],
        "query_string": b"",
    }
    return Request(scope, receive)


async def main():
    # ---------- 测试非流式 ----------
    req = make_request({
        "model": "sensenova-6.8-flash-lite",
        "messages": [
            {
                "role": "user",
                "content": "你好，做个自我介绍"
            }
        ],
        "stream": False,
    })
    resp = await handle_messages(req)
    print("=== 非流式响应 ===")
    print(resp.body.decode("utf-8"))

    # ---------- 测试流式 ----------
    # req = make_request({
    #     "model": "sensenova-6.8-flash-lite",
    #     "messages": [
    #         {
    #             "role": "user",
    #             "content": "写一首关于秋天的短诗"
    #         }
    #     ],
    #     "stream": True,
    # })
    # resp = await handle_messages(req)
    # print("\n=== 流式响应 ===")
    # async for chunk in resp.body_iterator:
    #     # chunk 是 bytes，直接打印
    #     print(chunk.decode("utf-8"), end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
