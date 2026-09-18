# handlers/util/OpenaiToAnthropic.py
"""
把 OpenAI Chat Completions 的响应（流式 / 非流式）转换成 Anthropic Messages API 格式。

覆盖：
- 文本增量
- 工具调用（tool_calls -> tool_use），含流式 arguments 增量拼接
- stop_reason 映射
- usage 透传
- 流中途异常：发 error 事件 + message_stop，避免裸 500
"""

import json
import uuid


def _sse(event: str, data: dict) -> bytes:
    """构造一条 Anthropic SSE 消息"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


# ============================================================
# 流式：OpenAI stream -> Anthropic SSE
# ============================================================
async def openai_stream_to_anthropic(stream, model_name: str):
    """异步生成器：把 OpenAI 流式 chunk 转成 Anthropic SSE 字节流"""

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # ---- message_start ----
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
        },
    })

    block_index = 0
    text_block_open = False
    # openai tool_call.index -> anthropic block index
    tool_block_index: dict = {}
    # openai tool_call.index -> 累积的 arguments 字符串
    tool_args_buf: dict = {}
    # openai tool_call.index -> {"id":..., "name":...}
    tool_meta: dict = {}

    stop_reason = "end_turn"
    output_tokens = 0
    input_tokens = 0

    try:
        async for chunk in stream:
            # ---- usage（有的实现只在最后一块给）----
            usage = getattr(chunk, "usage", None)
            if usage:
                it = getattr(usage, "prompt_tokens", None)
                ot = getattr(usage, "completion_tokens", None)
                if it is not None:
                    input_tokens = it
                if ot is not None:
                    output_tokens = ot

            if not getattr(chunk, "choices", None):
                continue

            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)

            # ---- 文本增量 ----
            if delta is not None and getattr(delta, "content", None):
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
            if delta is not None and getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    idx = getattr(tc, "index", 0) or 0

                    # 首次出现：先关掉文本块（文本块与工具块不能交叠）
                    if idx not in tool_block_index:
                        if text_block_open:
                            yield _sse("content_block_stop", {
                                "type": "content_block_stop",
                                "index": block_index,
                            })
                            text_block_open = False
                            block_index += 1

                        fn = getattr(tc, "function", None)
                        tool_meta[idx] = {
                            "id": getattr(tc, "id", None) or f"toolu_{uuid.uuid4().hex[:24]}",
                            "name": getattr(fn, "name", "") if fn else "",
                        }
                        tool_args_buf[idx] = ""
                        tool_block_index[idx] = block_index

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

                    # 增量 arguments
                    fn = getattr(tc, "function", None)
                    args_piece = getattr(fn, "arguments", None) if fn else None
                    if args_piece:
                        tool_args_buf[idx] += args_piece
                        yield _sse("content_block_delta", {
                            "type": "content_block_delta",
                            "index": tool_block_index[idx],
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": args_piece,
                            },
                        })

            # ---- finish_reason ----
            fr = getattr(choice, "finish_reason", None)
            if fr:
                stop_reason = {
                    "stop": "end_turn",
                    "length": "max_tokens",
                    "tool_calls": "tool_use",
                    "function_call": "tool_use",
                    "content_filter": "end_turn",
                }.get(fr, "end_turn")

    except Exception as e:
        # 流中途出错：发 error 事件 + message_stop，避免 FastAPI 裸 500
        print("openai_stream_to_anthropic 上游流式异常:", repr(e))
        # 尽量把已打开的块关掉
        if text_block_open:
            yield _sse("content_block_stop", {
                "type": "content_block_stop",
                "index": block_index,
            })
        for idx, blk_idx in tool_block_index.items():
            yield _sse("content_block_stop", {
                "type": "content_block_stop",
                "index": blk_idx,
            })

        yield _sse("error", {
            "type": "error",
            "error": {"type": "api_error", "message": f"上游流式异常: {e}"},
        })
        yield _sse("message_stop", {"type": "message_stop"})
        return

    # ---- 正常收尾：关闭所有打开的块 ----
    if text_block_open:
        yield _sse("content_block_stop", {
            "type": "content_block_stop",
            "index": block_index,
        })

    for idx, blk_idx in tool_block_index.items():
        yield _sse("content_block_stop", {
            "type": "content_block_stop",
            "index": blk_idx,
        })

    yield _sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    })
    yield _sse("message_stop", {"type": "message_stop"})


# ============================================================
# 非流式：OpenAI ChatCompletion -> Anthropic Message
# ============================================================
def openai_to_anthropic(resp, model_name: str) -> dict:
    """把 OpenAI ChatCompletion 转成 Anthropic Message"""
    choice = resp.choices[0]
    msg = choice.message
    content_blocks = []

    # ---- 文本 ----
    if getattr(msg, "content", None):
        content_blocks.append({"type": "text", "text": msg.content})

    # ---- 工具调用 ----
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            raw_args = getattr(fn, "arguments", None) if fn else None
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}
            content_blocks.append({
                "type": "tool_use",
                "id": getattr(tc, "id", None) or f"toolu_{uuid.uuid4().hex[:24]}",
                "name": getattr(fn, "name", "") if fn else "",
                "input": args,
            })

    # Anthropic 要求 content 至少有一个 block
    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    # ---- stop_reason ----
    stop_reason = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "function_call": "tool_use",
        "content_filter": "end_turn",
    }.get(getattr(choice, "finish_reason", None), "end_turn")

    # ---- usage ----
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
        },
    }