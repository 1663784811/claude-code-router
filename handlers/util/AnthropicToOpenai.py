"""
把 Anthropic Messages API 的请求体转换为 OpenAI Chat Completions 请求体
"""
import json
from typing import Any, Dict, List, Tuple


def _content_to_openai(content: Any) -> Tuple[str, List[Dict], List[Dict]]:
    """
    把 Anthropic 的 content 转成 OpenAI 的 (text, tool_calls, tool_results)
    - content 可能是 str，也可能是 list[block]
    - block 类型: text / image / tool_use / tool_result
    """
    text_parts: List[str] = []
    tool_calls: List[Dict] = []
    tool_results: List[Dict] = []

    if content is None:
        return "", tool_calls, tool_results

    if isinstance(content, str):
        return content, tool_calls, tool_results

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                text_parts.append(str(block))
                continue

            btype = block.get("type")

            if btype == "text":
                text_parts.append(block.get("text", ""))

            elif btype == "image":
                # Anthropic image -> OpenAI image_url (data url)
                src = block.get("source", {})
                if src.get("type") == "base64":
                    media = src.get("media_type", "image/png")
                    data = src.get("data", "")
                    # 这里以多模态文本形式表达，交由上层决定是否走 vision 模型
                    text_parts.append(
                        f"\n[image: data:{media};base64,{data[:64]}...]\n"
                    )
                elif src.get("type") == "url":
                    text_parts.append(f"\n[image: {src.get('url')}]\n")

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
                    sub_text, _, _ = _content_to_openai(tr_content)
                    tr_text = sub_text
                else:
                    tr_text = tr_content if isinstance(tr_content, str) else json.dumps(
                        tr_content, ensure_ascii=False
                    )
                tool_results.append({
                    "tool_call_id": block.get("tool_use_id", ""),
                    "content": tr_text or "",
                })

            else:
                # 未知类型，原样塞进文本
                text_parts.append(json.dumps(block, ensure_ascii=False))

    return "\n".join(p for p in text_parts if p), tool_calls, tool_results


def anthropic_to_openai_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 Anthropic /v1/messages 请求体转换为 OpenAI /v1/chat/completions 请求体
    """
    openai_messages: List[Dict] = []

    # 1) Anthropic 顶层 system -> OpenAI 首条 system 消息
    system = body.get("system")
    if system:
        if isinstance(system, list):
            sys_text, _, _ = _content_to_openai(system)
        else:
            sys_text = str(system)
        if sys_text:
            openai_messages.append({"role": "system", "content": sys_text})

    # 2) 逐条转换 messages
    for msg in body.get("messages", []) or []:
        role = msg.get("role", "user")
        content = msg.get("content")

        text, tool_calls, tool_results = _content_to_openai(content)

        # tool_result 必须单独成一条 role=tool 消息
        for tr in tool_results:
            openai_messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_call_id"],
                "content": tr["content"],
            })

        if role == "assistant":
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": text or None,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            # 如果既没文本也没 tool_calls，跳过
            if assistant_msg["content"] or tool_calls:
                openai_messages.append(assistant_msg)
        else:
            # user / 其他
            if text:
                openai_messages.append({"role": "user", "content": text})

    # 3) 参数映射
    openai_body: Dict[str, Any] = {
        "model": body.get("model", "sensenova-6.8-flash-lite"),
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