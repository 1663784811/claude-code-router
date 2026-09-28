"""
把 Anthropic Messages API 的请求体转换为 OpenAI Chat Completions 请求体

- text / image / tool_use / tool_result 都会转换
- image 转成 OpenAI 多模态 image_url（纯文本消息仍是 str，含图才用 list）
- thinking / redacted_thinking 直接丢弃，不回传上游
- model 为必填，缺失时抛 ValueError（由调用方转成 400）
"""
import json
from typing import Any, Dict, List, Tuple


def _parts_to_text(parts: List[Dict]) -> str:
    """只取文本部分的拼接结果（用于 system / tool_result 这类纯文本场景）"""
    return "\n".join(
        p["text"] for p in parts if p.get("type") == "text" and p.get("text")
    )


def _parts_to_content(parts: List[Dict]) -> Any:
    """
    把 content parts 收敛成 OpenAI 的 content 字段：
    - 全是文本 -> str（兼容只认纯文本的上游）
    - 含图片   -> list[part]（OpenAI 多模态格式）
    """
    if not parts:
        return ""
    if all(p.get("type") == "text" for p in parts):
        return _parts_to_text(parts)
    return parts


def _content_to_openai(content: Any) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    把 Anthropic 的 content 转成 OpenAI 的 (content_parts, tool_calls, tool_results)
    - content 可能是 str，也可能是 list[block]
    - block 类型: text / image / tool_use / tool_result / thinking
    - content_parts 是 OpenAI 的 content part 列表，用 _parts_to_content 收敛后再用
    """
    text_parts: List[Dict] = []
    tool_calls: List[Dict] = []
    tool_results: List[Dict] = []

    if content is None:
        return text_parts, tool_calls, tool_results

    if isinstance(content, str):
        if content:
            text_parts.append({"type": "text", "text": content})
        return text_parts, tool_calls, tool_results

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                text_parts.append({"type": "text", "text": str(block)})
                continue

            btype = block.get("type")

            if btype == "text":
                text_parts.append({"type": "text", "text": block.get("text", "")})

            elif btype in ("thinking", "redacted_thinking"):
                # 扩展思考块不回传给上游：原文塞进 prompt 会污染上下文，签名也不应外泄
                continue

            elif btype == "image":
                # Anthropic image -> OpenAI image_url (data url / 远程 url)
                src = block.get("source") or {}
                if src.get("type") == "base64":
                    media = src.get("media_type", "image/png")
                    data = src.get("data", "")
                    if data:
                        text_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{media};base64,{data}"},
                        })
                elif src.get("type") == "url":
                    url = src.get("url")
                    if url:
                        text_parts.append({
                            "type": "image_url",
                            "image_url": {"url": url},
                        })

            elif btype == "tool_use":
                try:
                    args = block.get("input", {})
                    if isinstance(args, str):
                        json.loads(args)  # 校验
                        args_str = args
                    else:
                        args_str = json.dumps(args, ensure_ascii=False)
                except Exception:
                    args_str = "{}"
                tool_calls.append({
                    "id": block.get("id") or f"call_{len(tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": args_str,
                    },
                })

            elif btype == "tool_result":
                # 工具结果在 OpenAI 中是一条独立的 role=tool 消息
                tr_content = block.get("content")
                if isinstance(tr_content, list):
                    # 递归取出 text
                    sub_parts, _, _ = _content_to_openai(tr_content)
                    tr_text = _parts_to_text(sub_parts)
                elif isinstance(tr_content, str):
                    tr_text = tr_content
                elif tr_content is None:
                    tr_text = ""
                else:
                    tr_text = json.dumps(tr_content, ensure_ascii=False)
                tool_results.append({
                    "tool_call_id": block.get("tool_use_id", "") or "",
                    "content": tr_text,
                })

            else:
                # 未知类型，原样塞进文本
                text_parts.append({
                    "type": "text",
                    "text": json.dumps(block, ensure_ascii=False),
                })

    return text_parts, tool_calls, tool_results


def anthropic_to_openai_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 Anthropic /v1/messages 请求体转换为 OpenAI /v1/chat/completions 请求体
    """
    openai_messages: List[Dict] = []

    # 1) Anthropic 顶层 system -> OpenAI 首条 system 消息
    system = body.get("system")
    if system:
        if isinstance(system, list):
            sys_parts, _, _ = _content_to_openai(system)
            sys_text = _parts_to_text(sys_parts)
        else:
            sys_text = str(system)
        if sys_text:
            openai_messages.append({"role": "system", "content": sys_text})

    # 上一条 assistant 消息发出的 tool_call id（按顺序），
    # 用于 Anthropic 侧 tool_result 没带 tool_use_id 时兜底
    last_tool_call_ids: List[str] = []

    # 2) 逐条转换 messages
    for msg in body.get("messages", []) or []:
        role = msg.get("role", "user")
        content = msg.get("content")

        parts, tool_calls, tool_results = _content_to_openai(content)
        content_value = _parts_to_content(parts)

        # tool_result 必须单独成一条 role=tool 消息
        for i, tr in enumerate(tool_results):
            cid = tr["tool_call_id"]
            if not cid and i < len(last_tool_call_ids):
                # 缺 tool_use_id：按顺序回退到上一条 assistant 的 tool_call id
                cid = last_tool_call_ids[i]
            if not cid:
                # 没有可匹配的 id，上游会 400，直接丢弃这条
                print("警告: tool_result 无可用 tool_call_id，已跳过:", tr["content"][:80])
                continue
            openai_messages.append({
                "role": "tool",
                "tool_call_id": cid,
                "content": tr["content"],
            })

        if role == "assistant":
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": content_value or None,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
                last_tool_call_ids = [tc["id"] for tc in tool_calls]
            else:
                last_tool_call_ids = []
            # 如果既没文本也没 tool_calls，跳过
            if assistant_msg["content"] or tool_calls:
                openai_messages.append(assistant_msg)
        else:
            # user / 其他
            last_tool_call_ids = []
            if content_value:
                openai_messages.append({"role": "user", "content": content_value})

    # 3) 参数映射
    # model 必须由客户端指定：这里不能塞默认值，否则会把别的 provider 的模型名
    # 发到当前上游端点，得到误导性的 404
    model = body.get("model")
    if not model or not str(model).strip():
        raise ValueError("请求缺少 model 字段")

    openai_body: Dict[str, Any] = {
        "model": model,
        "messages": openai_messages,
    }

    if body.get("stream") is not None:
        openai_body["stream"] = bool(body.get("stream"))

    # max_tokens -> max_tokens (OpenAI 兼容字段名一致)
    if body.get("max_tokens") is not None:
        openai_body["max_tokens"] = body["max_tokens"]

    # temperature / top_p 一致
    for key in ("temperature", "top_p"):
        if body.get(key) is not None:
            openai_body[key] = body[key]

    # stop_sequences -> stop
    if body.get("stop_sequences"):
        openai_body["stop"] = body["stop_sequences"]

    # tools 映射
    anth_tools = body.get("tools")
    if anth_tools:
        openai_tools = []
        for t in anth_tools:
            # Anthropic: {name, description, input_schema}
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            })
        openai_body["tools"] = openai_tools

        # tool_choice 映射
        tc = body.get("tool_choice")
        if tc:
            if isinstance(tc, dict):
                ttype = tc.get("type")
                if ttype == "auto":
                    openai_body["tool_choice"] = "auto"
                elif ttype == "any":
                    openai_body["tool_choice"] = "required"
                elif ttype == "tool":
                    openai_body["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tc.get("name", "")},
                    }
            elif isinstance(tc, str):
                openai_body["tool_choice"] = tc

    # metadata.user_id -> user
    meta = body.get("metadata") or {}
    if meta.get("user_id"):
        openai_body["user"] = meta["user_id"]

    # 过滤掉 OpenAI 不认识的顶层字段
    return openai_body