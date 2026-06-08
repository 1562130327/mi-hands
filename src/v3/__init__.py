"""
MI Hands v3.0 - 基于三层架构的智能桌面控制

核心设计：
1. 决策层 - 理解任务，规划步骤（MiMo 驱动）
2. 执行层 - 智能选择最优执行方式（UIA + pywinauto + pyautogui）
3. 验证层 - 检查结果，不合格重做（MiMo 验证）

运行模式：
- MCP 模式：作为插件被 Claude Code、Cursor 等 agent 调用
- 独立模式：独立运行（计划中）

专注于 MiMo 视觉模型
"""

__version__ = "3.0.0"
