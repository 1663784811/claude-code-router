# handlers/util/OpenaiToAnthropic.py
import json
import uuid


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


async def openai_stream_to_anthropic(stream, model_name: str):
    """异步生成器：把 OpenAI 流式 chunk 转成 Anthropic SSE 字节流"""
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    yield _sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": model_name,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    })

    block_index = 0
    text_block_open = False
    tool_block_open: dict = {}   # openai tool_call index -> anthropic block index
    tool_args_buf: dict = {}     # openai tool_call index -> 累积的 arguments 字符串
    tool_meta: dict = {}         # openai tool_call index -> {id, name}
    stop_reason = "end_turn"
    output_tokens = 0
    input_tokens = 0

    async for chunk in stream:
        # usage 可能挂在 chunk 上（有的实现只在最后一块给）
        usage = getattr(chunk, "usage", None)
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", None) or input_tokens
            output_tokens = getattr(usage, "completion_tokens", None) or output_tokens

        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta

        # ---- 文本增量 ----
        if getattr(delta, "content", None):
            if not text_block_open:
                yield _sse("content_block_start", {
                    "type": "content_block_start",
                    "index": block_index,
                    "content_block": {"type": "text", "text": ""},
                })
                text_block_open = True
            yield _sse("content_block_delta", {
                "type": "content_block_delta",
                "index": block_index,
                "delta": {"type": "text_delta", "text": delta.content},
            })

        # ---- 工具调用增量 ----
        if getattr(delta, "tool_calls", None):
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_block_open:
                    # 关闭文本块（工具块和文本块不能交叠）
                    if text_block_open:
                        yield _sse("content_block_stop", {
                            "type": "content_block_stop", "index": block_index,
                        })
                        text_block_open = False
                        block_index += 1

                    tool_meta[idx] = {
                        "id": tc.id or f"toolu_{uuid.uuid4().hex[:24]}",
                        "name": (tc.function.name if tc.function and tc.function.name else ""),
                    }
                    tool_args_buf[idx] = ""
                    tool_block_open[idx] = block_index

                    yield _sse("content_block_start", {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": tool_meta[idx]["id"],
                            "name": tool_meta[idx]["name"],
                            "input": {},
                        },
                    })
                    block_index += 1

                # 增量参数
                if tc.function and tc.function.arguments:
                    tool_args_buf[idx] += tc.function.arguments
                    yield _sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": tool_block_open[idx],
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": tc.function.arguments,
                        },
                    })

        if choice.finish_reason:
            stop_reason = {
                "stop": "end_turn",
                "length": "max_tokens",
                "tool_calls": "tool_use",
                "content_filter": "end_turn",
            }.get(choice.finish_reason, "end_turn")

    # ---- 收尾：关闭所有打开的块 ----
    if text_block_open:
        yield _sse("content_block_stop", {
            "type": "content_block_stop", "index": block_index,
        })
    for idx, blk_idx in tool_block_open.items():
        yield _sse("content_block_stop", {
            "type": "content_block_stop", "index": blk_idx,
        })

    yield _sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    })
    yield _sse("message_stop", {"type": "message_stop"})


def openai_to_anthropic(resp, model_name: str) -> dict:
    """把 OpenAI ChatCompletion 转成 Anthropic Message"""
    choice = resp.choices[0]
    msg = choice.message
    content_blocks = []

    if msg.content:
        content_blocks.append({"type": "text", "text": msg.content})

    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id or f"toolu_{uuid.uuid4().hex[:24]}",
                "name": tc.function.name,
                "input": args,
            })

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    stop_reason = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }.get(choice.finish_reason, "end_turn")

    usage = getattr(resp, "usage", None)
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        },
    }