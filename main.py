# main.py
from fastapi import FastAPI

from applicationConfig import SERVER_HOST, SERVER_PORT
from handlers import (
    handle_messages,
    handle_models,
    handle_model_detail,
    handle_rate_limits,
    handle_org_rate_limits,
    handle_other_v1_endpoints,
    proxy_all_requests,
    health_check,
    root,
    handle_options,
    handle_api_hello
)

app = FastAPI(title="Full Path Claude Proxy for Claude Code")
# ======================== 注册路由 ========================
app.api_route("/api/hello", methods=["GET", "HEAD"])(handle_api_hello)


# ---- 消息相关 API ----
app.post("/v1/messages")(handle_messages)
# ---- 模型相关 API ----
app.get("/v1/models")(handle_models)
app.get("/v1/models/{model_id}")(handle_model_detail)
# ---- 计费/配额相关 API ----
app.get("/v1/rate_limits")(handle_rate_limits)
app.get("/v1/organizations/{org_id}/rate_limits")(handle_org_rate_limits)
# ---- 其他 v1 路径 ----
app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])(handle_other_v1_endpoints)
# ---- 通用代理（捕获所有其他路径） ----
app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])(proxy_all_requests)
# ---- 健康检查和根路径 ----
app.get("/health")(health_check)
app.get("/")(root)
# ---- CORS 预检 ----
app.options("/{full_path:path}")(handle_options)

if __name__ == "__main__":
    import uvicorn
    # initApplicationFn()
    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, log_level="info", reload=True)
