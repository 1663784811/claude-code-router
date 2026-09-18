# handlers/base.py
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, Response

from applicationConfig import (
    CLAUDE_API_KEY,
    HTTP_PROXY,
    CORS_HEADERS
)


async def stream_upstream(resp: httpx.Response):
    """流式字节转发生成器"""
    async for chunk in resp.aiter_bytes():
        yield chunk


def build_upstream_headers(request: Request) -> dict:
    """构建上游请求头"""
    upstream_headers = {}
    for k, v in request.headers.items():
        lower_k = k.lower()
        if lower_k not in ["host", "content-length"]:
            upstream_headers[k] = v

    # 强制内置鉴权头
    upstream_headers["x-api-key"] = CLAUDE_API_KEY
    upstream_headers["anthropic-version"] = "2023-06-01"
    return upstream_headers


async def forward_request(target_url: str, method: str, headers: dict, body: bytes):
    """统一的请求转发函数"""
    client_opts = {}
    if HTTP_PROXY:
        client_opts["proxy"] = HTTP_PROXY

    try:
        async with httpx.AsyncClient(**client_opts, timeout=None) as client:
            # HEAD 请求特殊处理
            if method.upper() == "HEAD":
                upstream_resp = await client.head(
                    target_url, headers=headers, content=body
                )
                resp_headers = dict(upstream_resp.headers)
                resp_headers.update(CORS_HEADERS)
                return Response(
                    content=b"",
                    status_code=upstream_resp.status_code,
                    headers=resp_headers
                )

            # 其他方法使用 stream
            upstream_resp = await client.stream(
                method,
                target_url,
                headers=headers,
                content=body
            )

            resp_headers = dict(upstream_resp.headers)
            resp_headers.update(CORS_HEADERS)
            content_type = upstream_resp.headers.get("content-type", "")

            if "text/event-stream" in content_type:
                return StreamingResponse(
                    stream_upstream(upstream_resp),
                    status_code=upstream_resp.status_code,
                    headers=resp_headers,
                    media_type="text/event-stream"
                )
            else:
                content = await upstream_resp.aread()
                return Response(
                    content=content,
                    status_code=upstream_resp.status_code,
                    headers=resp_headers
                )

    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接 api.anthropic.com，请检查网络/代理设置")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理异常: {str(e)}")


async def health_check():
    """健康检查端点"""
    print('---------  health_check   ---')
    return {"status": "healthy", "service": "claude-proxy"}


async def root():
    """根路径信息"""
    print('---------  根路径信息 /  ---')
    return {
        "service": "Claude API Proxy",
        "version": "1.0.0",
        "endpoints": {
            "messages": "/v1/messages",
            "models": "/v1/models",
            "model_detail": "/v1/models/{model_id}",
            "rate_limits": "/v1/rate_limits",
            "org_rate_limits": "/v1/organizations/{org_id}/rate_limits",
            "health": "/health"
        }
    }


def handle_options(full_path: str):
    """处理 OPTIONS 预检请求"""
    print('---------  请求未处理地址  ---', full_path)
    return Response(status_code=204, headers=CORS_HEADERS)



