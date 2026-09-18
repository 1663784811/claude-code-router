# applicationConfig.py
import os
from pathlib import Path

# ======================== 环境变量配置 ========================
ENV_SETTINGS = {
    "ANTHROPIC_AUTH_TOKEN": "sk-bWLC27DtVEJ923jQPISltqPfobSmVjzQ",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.2",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "glm-5.2",
    "ANTHROPIC_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"
}



# ======================== Claude 代理配置 ========================

CLAUDE_BASE_URL = "https://token.sensenova.cn"
CLAUDE_API_KEY = "sk-AkBjsnJiWyZpixYdBjtQW9zAZFyNyq5h"
HTTP_PROXY = None  # 例如: "http://127.0.0.1:7890"






# ======================== 服务器配置 ========================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

# ======================== 配置文件路径 ========================
CLAUDE_DIR = Path.home() / '.claude'
SETTINGS_FILE = CLAUDE_DIR / 'settings.json'

# ======================== CORS 配置 ========================
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "*"
}




