"""MI Hands 入口"""

import asyncio
import argparse
import sys
from typing import List, Optional


async def main_async(args: argparse.Namespace):
    """异步主函数"""
    from .plugin_manager import PluginManager
    from .event_system import EventBus
    from ..plugins.wait.plugin import WaitPlugin
    from ..plugins.mouse_manager.plugin import MouseManagerPlugin
    from ..plugins.guide_manager.plugin import GuideManagerPlugin
    from ..plugins.github_sync.plugin import GitHubSyncPlugin
    from ..plugins.gui.plugin import GUIPlugin

    # 创建插件管理器
    event_bus = EventBus()
    plugin_manager = PluginManager(event_bus)

    # 注册插件
    await plugin_manager.register(WaitPlugin())
    await plugin_manager.register(MouseManagerPlugin())
    await plugin_manager.register(GuideManagerPlugin())
    await plugin_manager.register(GitHubSyncPlugin())

    # 如果启用 GUI
    if args.gui:
        gui_plugin = GUIPlugin()
        if await gui_plugin.initialize():
            await plugin_manager.register(gui_plugin)
            await gui_plugin.show_main_window()
            return

    # 如果启用 MCP
    if args.mcp:
        from ..plugins.server.plugin import ServerPlugin
        server_plugin = ServerPlugin()
        if await server_plugin.initialize():
            await plugin_manager.register(server_plugin)
            await server_plugin.start()
            return

    # 如果启用 API
    if args.api:
        from ..plugins.server.plugin import ServerPlugin
        server_plugin = ServerPlugin()
        if await server_plugin.initialize():
            await plugin_manager.register(server_plugin)
            await server_plugin.start_api()
            return

    # 如果指定了任务
    if args.task:
        guide_manager = plugin_manager.get_plugin("guide_manager")
        if guide_manager:
            guide = await guide_manager.get_guide(args.task)
            if guide:
                print(f"找到操作指南: {guide.name}")
                print(f"操作: {list(guide.operations.keys())}")
            else:
                print(f"未找到操作指南: {args.task}")
        return

    # 列出所有操作指南
    if args.list:
        guide_manager = plugin_manager.get_plugin("guide_manager")
        if guide_manager:
            guides = await guide_manager.list_guides()
            print(f"操作指南 ({len(guides)}):")
            for guide in guides:
                print(f"  - {guide}")
        return

    # 学习新应用
    if args.learn:
        guide_manager = plugin_manager.get_plugin("guide_manager")
        if guide_manager:
            guide = await guide_manager.learn_app(args.learn)
            if guide:
                print(f"学习完成: {guide.name}")
                await guide_manager.save_guide(guide.name, guide)
            else:
                print(f"学习失败: {args.learn}")
        return

    # 显示帮助
    parser.print_help()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MI Hands - MiMo 桌面控制 SDK",
        prog="mi-hands"
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="启用图形界面"
    )

    parser.add_argument(
        "--mcp",
        action="store_true",
        help="启用 MCP 服务器"
    )

    parser.add_argument(
        "--api",
        action="store_true",
        help="启用 OpenAI 兼容 API"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有操作指南"
    )

    parser.add_argument(
        "--task",
        type=str,
        help="执行指定任务"
    )

    parser.add_argument(
        "--learn",
        type=str,
        help="学习新应用"
    )

    args = parser.parse_args()

    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
