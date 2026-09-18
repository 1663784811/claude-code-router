# handlers/hello.py
from fastapi import Request, Response
from applicationConfig import CORS_HEADERS

async def handle_api_hello(request: Request):
    """本地直接响应 /api/hello GET/HEAD，不转发上游"""
    print(f'--------------- 处理：/api/hello {request.method} ---------------')
    print("请求头: \n", request.headers)
    body = await request.body()
    print("请求body: \n", body)

    # GET 返回标准 {"hello":"world"} JSON
    resp_body = b'{"hello":"world"}'
    # HEAD 请求只返回头，空body
    if request.method.upper() == "HEAD":
        return Response(
            content=resp_body,
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(resp_body)),
                **CORS_HEADERS
            }
        )
    # GET 请求返回完整json内容
    return Response(
        content=resp_body,
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(resp_body)),
            **CORS_HEADERS
        }
    )