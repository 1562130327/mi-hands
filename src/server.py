"""
MI Hands 服务层 — MCP Server + OpenAI 兼容 API

两种接入方式：
1. MCP Server — 给 Claude Code、Cursor 等 MCP 客户端用
2. OpenAI API — 给任何支持 OpenAI 格式的工具用（如 Codex++、Continue 等）
"""

import json
import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .uia_engine import UIAEngine
from .tools import get_tool_definitions, get_system_prompt, route_tool_call
from .optimizer import TokenOptimizer


# ============================================================
# OpenAI 兼容 API
# ============================================================

app = FastAPI(title="MI Hands", description="MiMo 桌面控制 SDK — OpenAI 兼容 API")

# UIA 引擎需要在使用时初始化（COM 线程问题）
_engine = None
optimizer = TokenOptimizer()

def get_engine() -> UIAEngine:
    """获取 UIA 引擎（懒加载，确保 COM 初始化）"""
    global _engine
    if _engine is None:
        import comtypes
        comtypes.CoInitialize()
        _engine = UIAEngine()
    return _engine


class ChatMessage(BaseModel):
    role: str
    content: str | list | None = None
    tool_calls: list | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "mi-hands"
    messages: list[ChatMessage]
    tools: list[dict] | None = None
    tool_choice: str | None = "auto"
    temperature: float = 1.0
    top_p: float = 0.95
    max_tokens: int = 4096
    stream: bool = False


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": "mi-hands",
                "object": "model",
                "owned_by": "mi-hands",
                "description": "MI Hands 桌面控制模型（UIA + Function Calling）",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI 兼容的聊天补全接口

    这个接口让外部工具（如 Codex++）可以通过标准 OpenAI API 调用 MI Hands。
    它不直接调 MiMo，而是把收到的 tool_calls 翻译成 UIA 操作执行。
    """
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    # 检查是否有 tool_calls 需要执行
    last_msg = messages[-1] if messages else {}

    # 如果最后一条消息包含 tool_calls，执行它们
    if last_msg.get("tool_calls"):
        eng = get_engine()
        results = []
        for tc in last_msg["tool_calls"]:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result_text = route_tool_call(eng, name, args)
            results.append({
                "tool_call_id": tc.get("id", ""),
                "role": "tool",
                "content": result_text,
            })

        return {
            "id": "mi-hands-local",
            "object": "chat.completion",
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": None,
                },
                "finish_reason": "tool_calls",
            }],
            "tool_results": results,
        }

    # 如果没有 tool_calls，返回当前屏幕状态
    eng = get_engine()
    snapshot = eng.get_snapshot()
    return {
        "id": "mi-hands-local",
        "object": "chat.completion",
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": snapshot,
            },
            "finish_reason": "stop",
        }],
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "engine": "uia"}


# ============================================================
# MCP Server（用 fastmcp）
# ============================================================

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("mi-hands", instructions="MI Hands 桌面控制工具，通过 UIA 控件树控制 Windows 桌面")

    @mcp.tool()
    def snapshot(mode: str = "uia") -> str:
        """获取当前屏幕状态。mode: uia(控件树)/screenshot(截图)/both(都要)"""
        eng = get_engine()
        if mode == "uia":
            return eng.get_snapshot()
        elif mode == "screenshot":
            ss = eng.take_screenshot()
            return f"[截图: {ss.width}x{ss.height}]"
        else:
            tree = eng.get_snapshot()
            ss = eng.take_screenshot()
            return f"{tree}\n\n[截图: {ss.width}x{ss.height}]"

    @mcp.tool()
    def click(x: int = 0, y: int = 0, index: int = -1, button: str = "left") -> str:
        """点击。用 index 精确点击控件，或用 x,y 坐标点击。"""
        eng = get_engine()
        if index >= 0:
            return eng.click_node(index)
        return eng.click(x, y, button)

    @mcp.tool()
    def type_text(text: str, index: int = -1) -> str:
        """输入文字。index 指定目标输入框。"""
        eng = get_engine()
        return eng.type_text(text, index if index >= 0 else None)

    @mcp.tool()
    def press_key(key: str) -> str:
        """按键。如 enter, tab, escape, backspace 等。"""
        eng = get_engine()
        return eng.press_key(key)

    @mcp.tool()
    def hotkey(keys: list[str]) -> str:
        """组合键。如 ['ctrl', 'c']。"""
        eng = get_engine()
        return eng.hotkey(keys)

    @mcp.tool()
    def scroll(x: int, y: int, delta: int) -> str:
        """滚动。delta 正数向上，负数向下。"""
        eng = get_engine()
        return eng.scroll(x, y, delta)

    @mcp.tool()
    def drag(x1: int, y1: int, x2: int, y2: int) -> str:
        """拖拽。"""
        eng = get_engine()
        return eng.drag(x1, y1, x2, y2)

    @mcp.tool()
    def list_windows() -> str:
        """列出所有可操作的窗口。"""
        eng = get_engine()
        windows = eng.list_windows()
        if not windows:
            return "没有找到可见窗口"
        lines = []
        for w in windows:
            focus = " (焦点)" if w["is_focused"] else ""
            lines.append(f"[{w['handle']}] {w['title']}{focus}")
        return "\n".join(lines)

    @mcp.tool()
    def activate_window(window_handle: int) -> str:
        """激活指定窗口。"""
        eng = get_engine()
        return eng.activate_window(window_handle)

    @mcp.tool()
    def run_task(task: str, max_turns: int = 20) -> str:
        """执行一个完整的桌面操作任务。AI 会自动循环操作直到完成。"""
        from .mimo_client import MiMoClient
        import os
        api_key = os.getenv("MIMO_API_KEY", "")
        if not api_key:
            return "错误: 未设置 MIMO_API_KEY 环境变量"
        client = MiMoClient(api_key=api_key, max_turns=max_turns)
        result = client.run_task(task)
        return json.dumps(result, ensure_ascii=False, indent=2)

    MCP_AVAILABLE = True

except ImportError:
    MCP_AVAILABLE = False
    mcp = None


# ============================================================
# 启动入口
# ============================================================

def start_api_server(host: str = "0.0.0.0", port: int = 8765):
    """启动 OpenAI 兼容 API 服务"""
    import uvicorn
    print(f"🚀 MI Hands API 启动: http://{host}:{port}")
    print(f"   POST /v1/chat/completions — OpenAI 兼容接口")
    print(f"   GET  /v1/models — 模型列表")
    print(f"   GET  /health — 健康检查")
    uvicorn.run(app, host=host, port=port)


def start_mcp_server():
    """启动 MCP Server（stdio 模式，不能 print 到 stdout）"""
    if not MCP_AVAILABLE:
        import sys
        sys.stderr.write("MCP not available: fastmcp not installed\n")
        return
    # stdio 模式下不能 print，会干扰 MCP 协议
    mcp.run()


def start_all(host: str = "0.0.0.0", port: int = 8765):
    """同时启动 API 和 MCP"""
    import threading
    import uvicorn

    # API 在后台线程
    api_thread = threading.Thread(
        target=uvicorn.run, args=(app,),
        kwargs={"host": host, "port": port},
        daemon=True,
    )
    api_thread.start()
    print(f"🚀 MI Hands API: http://{host}:{port}")

    # MCP 在主线程
    if MCP_AVAILABLE:
        print("🚀 MI Hands MCP Server 启动")
        mcp.run()
    else:
        print("⚠️ MCP 不可用，只运行 API")
        api_thread.join()
