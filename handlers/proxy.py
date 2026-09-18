# handlers/proxy.py
from fastapi import Request

from .base import forward_request, build_upstream_headers


async def handle_other_v1_endpoints(path: str, request: Request):
    """处理其他未明确映射的 /v1/* 路径"""
    target_url = f"/v1/{path}"
    print(f'处理其他 /v1 请求: {target_url}')
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, request.method, upstream_headers, body)


async def proxy_all_requests(full_path: str, request: Request):
    """处理所有其他路径的请求（通用代理）"""
    target_url = f"/{full_path}"
    print(f'代理所有请求: {target_url} {request.method} {request.url}')
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, request.method, upstream_headers, body)
