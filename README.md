# MI Hands v3.0

MiMo 桌面控制 SDK - AI 驱动的自进化桌面自动化

## 特性

- 🧠 **自进化系统** - 越用越聪明，成功/失败经验自动积累
- 🏗️ **三层架构** - 决策层(MiMo) + 执行层(多引擎) + 验证层(截图检查)
- 🔧 **32 个 MCP 工具** - 完整的桌面操作能力
- 🛡️ **安全加固** - 白名单机制、路径限制、操作日志
- 🔄 **学习循环** - 失败→反馈→重新规划→再执行
- 📊 **智能验证** - 截图对比、UIA 树分析、失败诊断

## 架构

```
MCP 插件层 (32 工具)
    ↓
自进化系统 (经验管理 + 学习循环 + 智能验证)
    ↓
三层架构 (决策层 + 执行层 + 验证层)
    ↓
底层引擎 (UIA + pyautogui + Win32 + PIL)
```

## 安装

```bash
pip install mi-hands
```

## 配置

### 设置 MiMo API Key

```bash
export MIMO_API_KEY="your-api-key"
```

### MCP 配置（以 Claude Code 为例）

在 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "mi-hands": {
      "command": "python",
      "args": ["-m", "src.v3.mcp.plugin"]
    }
  }
}
```

## 使用

### 基本操作

```python
# 通过 MCP 调用
from src.v3.mcp.plugin import create_mcp_server

mcp = create_mcp_server()
# 然后可以通过 MCP 协议调用工具
```

### 可用工具（32 个）

| 类别 | 工具 |
|------|------|
| **核心** | run_task, snapshot, analyze_screen |
| **点击** | click, double_click, scroll, drag |
| **输入** | type_text, press_key, hotkey |
| **绘制** | draw_path, draw_curve, draw_circle |
| **窗口** | list_windows, activate_window |
| **文件** | read_file, write_file, list_files |
| **脚本** | execute_script |
| **Skill** | find_skill, install_skill, list_skills |
| **监控** | get_metrics, get_action_history, rollback |
| **记忆** | get_memory_stats, get_learning_stats |

### 自进化系统

MI Hands v3.0 的核心特性是**自进化**：

1. **成功经验记录** - 操作成功后自动记录步骤
2. **失败经验学习** - 操作失败后记录原因和改进方向
3. **智能验证** - 截图检查是否真正完成任务
4. **学习循环** - 失败时自动重新规划

```python
# 示例：刷抖音
# 第一次：AI 尝试用 scroll()，失败
# 记录经验：scroll() 不适用于抖音桌面版
# 第二次：AI 用 press('down')，成功
# 记录经验：抖音桌面版用键盘切换视频
# 第三次：直接复用成功经验
```

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_verify.py -v
```

## 项目结构

```
MI-Hands/
├── src/v3/
│   ├── core/              # 核心模块（18 个）
│   │   ├── host_agent.py  # 决策层
│   │   ├── app_agent.py   # 执行层
│   │   ├── verify.py      # 验证层
│   │   ├── experience_manager.py  # 经验管理
│   │   ├── learning_loop.py       # 学习循环
│   │   └── smart_verify.py        # 智能验证
│   └── mcp/
│       └── plugin.py      # MCP 插件（32 个工具）
├── experience/            # 经验存储
├── tests/                 # 测试（136 个）
└── README.md
```

## 贡献

欢迎贡献代码！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 许可证

MIT License

## 更新日志

### v3.0.0 (2026-06-08)

- 🎉 全新自进化系统
- 🏗️ 重构为三层架构
- 🛡️ 安全加固（白名单、路径限制）
- 🧪 136 个测试全部通过
- 📦 32 个 MCP 工具

### v2.0.0 (2026-06-05)

- 🧩 插件架构
- 📚 操作指南库
- 🌐 GitHub 社区
