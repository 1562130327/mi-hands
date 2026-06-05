"""插件管理器"""

from typing import Dict, Optional, List
from .interfaces import PluginInterface
from .event_system import EventBus


class PluginManager:
    """插件管理器"""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._plugins: Dict[str, PluginInterface] = {}
        self._event_bus = event_bus or EventBus()

    async def register(self, plugin: PluginInterface) -> bool:
        """注册插件"""
        try:
            # 检查依赖
            for dep in plugin.dependencies:
                if dep not in self._plugins:
                    raise Exception(f"依赖插件 {dep} 未加载")

            # 初始化插件
            if await plugin.initialize():
                self._plugins[plugin.name] = plugin
                return True
            return False

        except Exception as e:
            print(f"注册插件 {plugin.name} 失败: {e}")
            return False

    async def unregister(self, plugin_name: str):
        """注销插件"""
        if plugin_name in self._plugins:
            await self._plugins[plugin_name].shutdown()
            del self._plugins[plugin_name]

    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """获取插件"""
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self._plugins.keys())

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        return self._event_bus
