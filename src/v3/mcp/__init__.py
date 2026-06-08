"""
MCP 适配层 - 让 MI Hands 能被所有支持 MCP 的 agent 应用调用

支持的应用：
- Claude Code
- Cursor
- VS Code (Copilot)
- Windsurf
- Cline
- Continue
- 等等...
"""

from .plugin import MCPPlugin

__all__ = ["MCPPlugin"]
