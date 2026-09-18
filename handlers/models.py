# handlers/models.py
from fastapi import Request
from .base import forward_request, build_upstream_headers


async def handle_models(request: Request):
    """处理 /v1/models 路径的请求"""
    print('--------------- 处理： /v1/models ---------------')
    target_url = f"/v1/models"
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, "GET", upstream_headers, body)


async def handle_model_detail(model_id: str, request: Request):
    """处理 /v1/models/{model_id} 路径的请求"""
    print(f'--------------- 处理： /v1/models/{model_id} ---------------')
    target_url = f"/v1/models/{model_id}"
    body = await request.body()
    upstream_headers = build_upstream_headers(request)
    return await forward_request(target_url, "GET", upstream_headers, body)