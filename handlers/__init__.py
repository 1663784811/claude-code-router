# 处理器导出
# 新增 /api/hello 处理器
from .hello import handle_api_hello
# 消息相关处理器 - 处理 /v1/messages 路径的请求
from .messages import handle_messages
# 模型相关处理器 - 处理 /v1/models 和 /v1/models/{model_id} 路径的请求
from .models import handle_models, handle_model_detail
# 速率限制相关处理器 - 处理 /v1/rate_limits 和 /v1/organizations/{org_id}/rate_limits 路径的请求
from .rate_limits import handle_rate_limits, handle_org_rate_limits
# 通用代理处理器 - 处理未明确匹配的其他路径请求
from .proxy import proxy_all_requests, handle_other_v1_endpoints
# 基础功能处理器 - 提供健康检查、根路径和 CORS 预检等基础功能
from .base import health_check, root, handle_options
# ======================== 导出接口 ========================

__all__ = [
    "handle_api_hello",

    # ---- 消息相关 ----
    'handle_messages',  # 处理消息请求 (POST /v1/messages)

    # ---- 模型相关 ----
    'handle_models',  # 获取模型列表 (GET /v1/models)
    'handle_model_detail',  # 获取特定模型详情 (GET /v1/models/{model_id})

    # ---- 速率限制相关 ----
    'handle_rate_limits',  # 获取速率限制 (GET /v1/rate_limits)
    'handle_org_rate_limits',  # 获取组织速率限制 (GET /v1/organizations/{org_id}/rate_limits)

    # ---- 代理相关 ----
    'proxy_all_requests',  # 通用代理，捕获所有未匹配的路径
    'handle_other_v1_endpoints',  # 处理其他 /v1/* 路径的请求

    # ---- 系统功能 ----
    'health_check',  # 健康检查端点 (GET /health)
    'root',  # 根路径信息 (GET /)
    'handle_options',  # CORS 预检请求处理 (OPTIONS /{full_path:path})

]
