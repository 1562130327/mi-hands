"""
工具定义 — MiMo Function Calling 的 tools 定义和路由

10 个工具：
- snapshot: 获取屏幕状态（UIA 树 / 截图 / 两者）
- click: 点击坐标或控件索引
- type_text: 输入文字
- press_key: 按键
- hotkey: 组合键
- scroll: 滚动
- drag: 拖拽
- list_windows: 列出可操作窗口
- activate_window: 激活窗口
- done: 任务完成
"""

from typing import Any

# ============================================================
# MiMo Function Calling 工具定义
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "snapshot",
            "description": "获取当前屏幕状态。默认返回 UIA 控件树文本（便宜），也可截图或两者都要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["uia", "screenshot", "both"],
                        "description": "uia=控件树文本(默认,省token), screenshot=截图, both=都要"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "点击屏幕上的位置。可以用坐标(x,y)或控件索引(index，从 snapshot 的 UI 树中获取)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "点击的 X 坐标"},
                    "y": {"type": "integer", "description": "点击的 Y 坐标"},
                    "index": {"type": "integer", "description": "控件索引（从 UI 树的 [数字] 获取，优先使用，比坐标更准）"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "鼠标按键，默认 left"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "输入文字。支持中文。可指定 index 先聚焦到输入框。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要输入的文字"},
                    "index": {"type": "integer", "description": "目标输入框的控件索引（可选，不填则在当前焦点输入）"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "按一个键。常用值: enter, tab, escape, backspace, delete, space, up, down, left, right, home, end, pageup, pagedown, f1-f12",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "要按的键名"}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "按组合键。如 ['ctrl', 'c'] 复制，['alt', 'f4'] 关闭窗口。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "键名列表，如 ['ctrl', 'shift', 's']"
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "在指定位置滚动。delta 正数向上，负数向下。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "滚动位置 X"},
                    "y": {"type": "integer", "description": "滚动位置 Y"},
                    "delta": {"type": "integer", "description": "滚动量，正数向上，负数向下，一般 3-5"}
                },
                "required": ["x", "y", "delta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "从一个位置拖拽到另一个位置。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer", "description": "起点 X"},
                    "y1": {"type": "integer", "description": "起点 Y"},
                    "x2": {"type": "integer", "description": "终点 X"},
                    "y2": {"type": "integer", "description": "终点 Y"}
                },
                "required": ["x1", "y1", "x2", "y2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "列出当前所有可操作的窗口。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_window",
            "description": "激活（切换到）指定窗口。",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_handle": {"type": "integer", "description": "窗口句柄（从 list_windows 获取）"}
                },
                "required": ["window_handle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "任务完成。调用此工具表示你已经完成了用户的任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "任务完成的简要总结"}
                },
                "required": ["summary"]
            }
        }
    },
]

# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """你是 MI Hands，一个 Windows 桌面操作助手。你可以通过工具调用来控制电脑。

工作流程：
1. 先用 snapshot 获取屏幕状态（默认用 UIA 控件树，省 token）
2. 分析 UI 树，找到要操作的控件
3. 用 click/type_text 等工具操作
4. 再用 snapshot 确认操作结果
5. 重复直到任务完成，最后调用 done

重要规则：
- 优先用 index（控件索引）操作，比坐标更准
- 输入中文时用 type_text，它会用剪贴板粘贴
- 如果 UIA 树看不清，用 snapshot(mode="screenshot") 截图
- 每次操作后用 snapshot 确认结果
- 不要猜测，看清楚再操作
"""


# ============================================================
# 工具路由
# ============================================================

def get_tool_definitions() -> list[dict]:
    """获取 MiMo Function Calling 的工具定义"""
    return TOOLS


def get_system_prompt() -> str:
    """获取系统提示词"""
    return SYSTEM_PROMPT


def route_tool_call(engine, name: str, arguments: dict[str, Any]) -> str:
    """路由工具调用到 UIA 引擎"""
    if name == "snapshot":
        mode = arguments.get("mode", "uia")
        if mode == "uia":
            return engine.get_snapshot()
        elif mode == "screenshot":
            ss = engine.take_screenshot()
            return f"[截图已生成: {ss.width}x{ss.height}]"
        else:  # both
            tree_text = engine.get_snapshot()
            ss = engine.take_screenshot()
            return f"{tree_text}\n\n[截图已生成: {ss.width}x{ss.height}]"

    elif name == "click":
        index = arguments.get("index")
        if index is not None:
            return engine.click_node(index)
        x = arguments.get("x", 0)
        y = arguments.get("y", 0)
        button = arguments.get("button", "left")
        return engine.click(x, y, button)

    elif name == "type_text":
        text = arguments.get("text", "")
        index = arguments.get("index")
        return engine.type_text(text, index)

    elif name == "press_key":
        return engine.press_key(arguments.get("key", "enter"))

    elif name == "hotkey":
        return engine.hotkey(arguments.get("keys", []))

    elif name == "scroll":
        return engine.scroll(
            arguments.get("x", 0),
            arguments.get("y", 0),
            arguments.get("delta", 0),
        )

    elif name == "drag":
        return engine.drag(
            arguments.get("x1", 0), arguments.get("y1", 0),
            arguments.get("x2", 0), arguments.get("y2", 0),
        )

    elif name == "list_windows":
        windows = engine.list_windows()
        if not windows:
            return "没有找到可见窗口"
        lines = []
        for w in windows:
            focus = " (焦点)" if w["is_focused"] else ""
            lines.append(f"  [{w['handle']}] {w['title']}{focus}")
        return "当前窗口:\n" + "\n".join(lines)

    elif name == "activate_window":
        return engine.activate_window(arguments.get("window_handle", 0))

    elif name == "done":
        return f"任务完成: {arguments.get('summary', '')}"

    else:
        return f"未知工具: {name}"
