# MI Hands — 设计文档

> 为小米 MiMo 模型专门优化的 Windows 桌面控制 SDK
> 日期：2026-06-05

## 1. 项目定位

MI Hands 是一个**专门为 MiMo 模型优化**的 Windows 桌面控制 SDK，通过 MCP + OpenAI API 暴露给各大 AI 工具使用。

### 核心理念

- **MiMo 优先**：利用 MiMo 的 Function Calling、图片理解、深度思考等能力
- **Token 节省**：默认用 UIA 控件树（文本），不用截图（图片），省 60-75% token
- **通用接口**：MCP + OpenAI API 双接口，让 Claude Code、Cursor 等都能调用
- **集百家之长**：参考 Windows-MCP、terminator、UFO、OpenAI 插件等成熟方案

## 2. 架构设计

```
用户/其他AI工具
    ↓
┌─────────────────────────────────────┐
│         MI Hands 主进程 (Python)      │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ MCP Server│  │ OpenAI 兼容 API  │ │
│  │ (stdio/  │  │ (FastAPI)        │ │
│  │  SSE)    │  │                  │ │
│  └─────┬────┘  └────────┬─────────┘ │
│        └────────┬───────┘           │
│        ┌────────┴────────┐          │
│        │  MiMo Function  │          │
│        │  Calling 调度层  │          │
│        └────────┬────────┘          │
│        ┌────────┴────────┐          │
│        │ 工作流引擎       │          │
│        │ (确定性脚本执行)  │          │
│        └────────┬────────┘          │
│        ┌────────┴────────┐          │
│        │ Token 优化器     │          │
│        │ (裁剪/Diff/压缩) │          │
│        └────────┬────────┘          │
│        ┌────────┴────────┐          │
│        │ Named Pipe 通信  │          │
│        └────────┬────────┘          │
└─────────────────┼───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│      mi-hands-helper (Node.js)      │
│  ┌──────────────┐ ┌──────────────┐  │
│  │ UIA 控件树    │ │ 输入注入      │  │
│  │ (读取/裁剪)  │ │ (点击/打字)   │  │
│  └──────────────┘ └──────────────┘  │
│  ┌──────────────┐ ┌──────────────┐  │
│  │ 截图          │ │ 窗口管理      │  │
│  │ (WGC)        │ │ (激活/列表)   │  │
│  └──────────────┘ └──────────────┘  │
└─────────────────────────────────────┘
```

### 三层分离

| 层 | 职责 | 语言 |
|---|------|------|
| Python 主进程 | MCP/API/MiMo 调用/业务逻辑 | Python |
| Node.js helper | Windows 操作/UIA/截图 | JavaScript |
| Named Pipe | 两层之间的桥梁 | 二进制帧 + JSON-RPC |

## 3. MiMo Function Calling 集成

### 为什么用 Function Calling

现有方案让 MiMo 输出 JSON 来描述操作，然后我们解析 JSON。问题是：
- MiMo 可能输出格式不对的 JSON
- 每次都要解析、容错
- 浪费 token 在格式约束上

Function Calling 是 MiMo 的原生能力：
- MiMo 直接返回结构化的 tool_calls
- 不用猜格式，不用解析
- 支持多轮对话

### 工具定义

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "snapshot",
            "description": "获取屏幕状态。默认返回UIA控件树文本，可选截图",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["uia", "screenshot", "both"],
                        "description": "uia=控件树文本(默认), screenshot=截图, both=都要"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "点击屏幕坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X坐标"},
                    "y": {"type": "integer", "description": "Y坐标"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "输入文字",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要输入的文字"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "按下键盘按键",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "按键名，如enter, tab, escape, backspace"}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "按下组合键",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "按键列表，如['ctrl', 'c']"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "滚动鼠标滚轮",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X坐标"},
                    "y": {"type": "integer", "description": "Y坐标"},
                    "delta": {"type": "integer", "description": "滚动量，正数向上，负数向下"}
                },
                "required": ["x", "y", "delta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "拖拽操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer", "description": "起始X"},
                    "y1": {"type": "integer", "description": "起始Y"},
                    "x2": {"type": "integer", "description": "结束X"},
                    "y2": {"type": "integer", "description": "结束Y"}
                },
                "required": ["x1", "y1", "x2", "y2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "列出所有可操作的窗口",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_window",
            "description": "激活指定窗口",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_id": {"type": "integer", "description": "窗口ID"}
                },
                "required": ["window_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "任务完成",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "任务完成总结"}
                }
            }
        }
    }
]
```

## 4. Token 优化策略

### 4.1 UIA 树裁剪

**目标**：把 400 节点的完整 UIA 树裁剪到 30-50 个有用节点。

**裁剪规则**：
- 保留：可点击、可输入、有文字的元素
- 去掉：装饰性元素、不可见元素、重复嵌套的容器
- 合并：连续的文本节点合并为一个

**格式**：
```
[0] Window: "记事本", App: notepad.exe
  [1] MenuBar "文件"
    [2] MenuItem "新建" (clickable)
    [3] MenuItem "打开" (clickable)
  [4] Edit "无标题 - 记事本" (editable, focused)
  [5] StatusBar "第 1 行, 第 1 列"
```

### 4.2 Diff 更新

**目标**：第二轮起只传变化部分，不重复传完整的 UIA 树。

**实现**：
- 保存上一轮的 UIA 树快照
- 对比新旧快照，找出差异
- 只把差异传给 MiMo

**示例**：
```
[变化] Edit [4] 内容从 "" 变为 "hello world"
[新增] Dialog "保存" (新窗口)
```

### 4.3 工具定义精简

- description 尽量短
- parameters 只列必要的字段
- 去掉不必要的 type 描述

### 4.4 System Prompt 压缩

```
旧版（~200 tokens）：
你是一个Windows桌面操作助手。用户会给你一个任务和屏幕截图，你需要分析截图并决定下一步操作...
（长篇大论）

新版（~50 tokens）：
你是MI Hands，控制Windows桌面。用提供的工具操作屏幕。默认用snapshot(mode="uia")获取状态。
```

### 4.5 截图按需

- 默认模式：UIA 控件树（~500 tokens）
- 降级条件：UIA 返回空/不完整时，自动切换到截图模式
- 手动触发：MiMo 可以主动调用 `snapshot(mode="screenshot")`

### Token 消耗对比

| 场景 | 每轮 tokens | 10轮任务 |
|------|------------|---------|
| 纯 UIA + Function Call | ~1500 | ~15,000 |
| UIA + 思考模式 | ~2500 | ~25,000 |
| 截图兜底模式 | ~3500 | ~35,000 |
| 旧方案（截图+JSON） | ~6000 | ~60,000 |

## 5. Node.js Helper 设计

### 5.1 UIA 控件树读取

使用 Windows UI Automation API 读取控件树：

```javascript
// 使用 @aspect-build/rules_ts 或直接调 COM
const tree = await readUIATree(windowHandle);
const pruned = pruneTree(tree, {
  keepClickable: true,
  keepEditable: true,
  keepTextual: true,
  maxDepth: 5,
  maxNodes: 50
});
```

### 5.2 输入注入

使用 robotjs 或 nut-tree：
```javascript
await click(x, y, button);
await typeText(text);
await pressKey(key);
await hotkey(keys);
```

### 5.3 截图

使用 Windows.Graphics.Capture（WGC）：
```javascript
const screenshot = await captureWindow(windowHandle);
// 返回 base64 PNG
```

### 5.4 Named Pipe 通信

参考 OpenAI 插件的 `NativePipeComputerUseTransport`：
- JSON-RPC 2.0 协议
- 4 字节长度头 + UTF-8 JSON 负载
- 请求/响应模式，自增 ID 匹配

## 6. MCP Server 设计

```json
// mcp-manifest.json
{
  "name": "mi-hands",
  "version": "1.0.0",
  "description": "MiMo 桌面控制 SDK",
  "tools": [
    {"name": "snapshot", "description": "获取屏幕状态"},
    {"name": "click", "description": "点击坐标"},
    {"name": "type_text", "description": "输入文字"},
    {"name": "press_key", "description": "按键"},
    {"name": "hotkey", "description": "组合键"},
    {"name": "scroll", "description": "滚动"},
    {"name": "drag", "description": "拖拽"},
    {"name": "list_windows", "description": "列出窗口"},
    {"name": "activate_window", "description": "激活窗口"},
    {"name": "done", "description": "任务完成"}
  ]
}
```

## 7. OpenAI 兼容 API 设计

```
POST /v1/chat/completions
{
  "model": "mi-hands",
  "messages": [...],
  "tools": [...],  // 自动注入 MI Hands 工具
  "tool_choice": "auto"
}
```

代理模式：接收请求 → 注入 MI Hands 工具 → 转发给 MiMo API → 执行 tool_calls → 返回结果

## 8. 目录结构

```
D:\MI-Hands\
├── src/                        # Python 主进程
│   ├── server.py              # MCP Server + OpenAI API
│   ├── mimo_client.py         # MiMo API 封装
│   ├── tools.py               # 工具定义和路由
│   ├── workflow.py            # 确定性工作流引擎
│   ├── optimizer.py           # Token 优化器
│   └── pipe_client.py         # Named Pipe 通信
├── helper/                     # Node.js helper
│   ├── index.mjs              # 入口
│   ├── uia.mjs                # UIA 控件树
│   ├── input.mjs              # 输入注入
│   ├── screenshot.mjs         # 截图
│   └── window.mjs             # 窗口管理
├── config/
│   └── mimo_config.yaml
├── workflows/                  # 预定义工作流脚本
├── mcp-manifest.json
├── requirements.txt
├── package.json
└── README.md
```

## 9. 参考项目

| 项目 | Stars | 借鉴什么 |
|------|-------|---------|
| Windows-MCP | 5.9k | Snapshot 工具、UIA 树结构 |
| terminator | 1.5k | 确定性工作流 |
| microsoft/UFO | 8.9k | UIA+Win32+WinCOM 混合检测 |
| uia-agent | 0 | 极简设计、控件树裁剪 |
| OpenAI computer-use | - | Named Pipe 通信、SKILL.md 设计 |

## 10. MiMo 特有优化

| MiMo 能力 | MI Hands 怎么用 |
|-----------|----------------|
| Function Calling | 操作定义为 tools，MiMo 直接调用 |
| 图片理解（mimo-v2.5） | UIA 读不到时截图兜底 |
| 深度思考 | 复杂任务自动启用 reasoning |
| reasoning_content | 多轮对话保留推理上下文 |

---

*设计完成：2026-06-05*
