# MI Hands v2.0

MiMo 桌面控制 SDK - 插件架构版本

## 特性

- 🧩 插件架构 - 模块化设计，易于扩展
- 📚 操作指南库 - 预置 30+ 常用应用
- 🧠 智能学习 - 自动学习新应用
- 🐭 鼠标共存 - 暂停/继续功能
- ⏱️ 等待工具 - 智能等待 UI 变化
- 🌐 GitHub 社区 - 社区共享操作指南

## 安装

```bash
pip install mi-hands
```

## 快速开始

```bash
# 首次配置
mi-hands --setup

# 启动服务
mi-hands --start
```

## 使用

```python
from core.plugin_manager import PluginManager
from plugins.guide_manager.plugin import GuideManagerPlugin

# 创建插件管理器
pm = PluginManager()
await pm.register(GuideManagerPlugin())

# 获取操作指南
guide_manager = pm.get_plugin("guide_manager")
guide = await guide_manager.get_guide("wechat")
```

## 插件列表

| 插件 | 说明 |
|------|------|
| `wait` | 等待 UI 变化 |
| `mouse_manager` | 鼠标暂停/继续 |
| `guide_manager` | 操作指南管理 |
| `uia_engine` | UIA 控件树 |
| `mimo_client` | MiMo 调用 |
| `server` | MCP + API 服务 |
| `github_sync` | GitHub 同步 |
| `gui` | 图形界面 |

## 操作指南库

预置应用：

- 微信、QQ、钉钉、飞书
- Chrome、Edge、Firefox
- Word、Excel、PowerPoint、WPS
- 记事本、计算器、文件管理器
- VS Code、PyCharm
- ...

## 贡献

欢迎贡献操作指南！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 许可证

MIT License
