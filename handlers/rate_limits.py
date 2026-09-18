# handlers/rate_limits.py
from fastapi import Request
from .base import forward_request, build_upstream_headers


async def handle_rate_limits(request: Request):
    """处理 /v1/rate_limits 路径的请求"""
    print('--------------- 处理： /v1/rate_limits ---------------')
    target_url = f"/v1/rate_limits"
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, "GET", upstream_headers, body)


async def handle_org_rate_limits(org_id: str, request: Request):
    """处理 /v1/organizations/{org_id}/rate_limits 路径的请求"""
    print(f'--------------- 处理： /v1/organizations/{org_id}/rate_limits ---------------')
    target_url = f"/v1/organizations/{org_id}/rate_limits"
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, "GET", upstream_headers, body)