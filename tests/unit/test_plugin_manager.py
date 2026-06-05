"""插件管理器测试"""

import pytest
from core.plugin_manager import PluginManager
from core.interfaces import PluginInterface


class MockPlugin(PluginInterface):
    """模拟插件"""

    name = "mock_plugin"
    version = "1.0.0"
    dependencies = []

    def __init__(self):
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> bool:
        self.initialized = True
        return True

    async def shutdown(self):
        self.shutdown_called = True

    async def get_status(self):
        return {"initialized": self.initialized}


@pytest.fixture
def plugin_manager():
    return PluginManager()


@pytest.mark.asyncio
async def test_register_plugin(plugin_manager):
    """测试注册插件"""
    plugin = MockPlugin()
    await plugin_manager.register(plugin)

    assert plugin_manager.get_plugin("mock_plugin") == plugin
    assert plugin.initialized is True


@pytest.mark.asyncio
async def test_unregister_plugin(plugin_manager):
    """测试注销插件"""
    plugin = MockPlugin()
    await plugin_manager.register(plugin)
    await plugin_manager.unregister("mock_plugin")

    assert plugin_manager.get_plugin("mock_plugin") is None
    assert plugin.shutdown_called is True


@pytest.mark.asyncio
async def test_get_plugin(plugin_manager):
    """测试获取插件"""
    plugin = MockPlugin()
    await plugin_manager.register(plugin)

    result = plugin_manager.get_plugin("mock_plugin")
    assert result == plugin

    result = plugin_manager.get_plugin("nonexistent")
    assert result is None
