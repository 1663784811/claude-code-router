# InitApplication.py
import json
import os
from pathlib import Path
from applicationConfig import ENV_SETTINGS, CLAUDE_DIR, SETTINGS_FILE


def initClaudeSettings():
    print("init claude settings")
    # 确保目录存在
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

    # 构建 env 配置格式
    env_config = {"env": ENV_SETTINGS}

    # 读取现有配置或创建新配置
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            print(f"已读取现有配置文件: {SETTINGS_FILE}")
        except json.JSONDecodeError:
            print(f"配置文件格式错误，将重新创建: {SETTINGS_FILE}")
            settings = {}
        except Exception as e:
            print(f"读取配置文件失败: {e}，将创建新配置")
            settings = {}
    else:
        print(f"配置文件不存在，将创建: {SETTINGS_FILE}")
        settings = {}

    # 更新 env 配置
    if "env" not in settings:
        settings["env"] = {}

    # 更新环境变量设置（保留已有配置，只更新指定的键）
    settings["env"].update(env_config["env"])

    # 保存配置文件
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"配置文件已成功保存: {SETTINGS_FILE}")
        print(f"已设置的环境变量: {settings}")
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        raise

    # 将环境变量设置到当前进程环境
    for key, value in ENV_SETTINGS.items():
        os.environ[key] = value

    return settings


def initApplicationFn():
    print("第一步: 初始化应用")
    initClaudeSettings()