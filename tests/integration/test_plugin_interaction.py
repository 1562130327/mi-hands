"""插件交互集成测试"""

import pytest
import pytest_asyncio
import tempfile
from core.plugin_manager import PluginManager
from core.event_system import EventBus
from plugins.wait.plugin import WaitPlugin
from plugins.mouse_manager.plugin import MouseManagerPlugin
from plugins.guide_manager.plugin import GuideManagerPlugin


@pytest_asyncio.fixture
async def plugin_system():
    """创建插件系统"""
    with tempfile.TemporaryDirectory() as tmpdir:
        event_bus = EventBus()
        plugin_manager = PluginManager(event_bus)

        # 注册插件
        await plugin_manager.register(WaitPlugin())
        await plugin_manager.register(MouseManagerPlugin())
        await plugin_manager.register(GuideManagerPlugin(guides_dir=tmpdir))

        yield plugin_manager, event_bus


@pytest.mark.asyncio
async def test_plugin_system_initialization(plugin_system):
    """测试插件系统初始化"""
    plugin_manager, event_bus = plugin_system

    assert len(plugin_manager.list_plugins()) == 3
    assert "wait" in plugin_manager.list_plugins()
    assert "mouse_manager" in plugin_manager.list_plugins()
    assert "guide_manager" in plugin_manager.list_plugins()


@pytest.mark.asyncio
async def test_mouse_pause_with_guide(plugin_system):
    """测试鼠标暂停与操作指南交互"""
    plugin_manager, event_bus = plugin_system

    mouse_manager = plugin_manager.get_plugin("mouse_manager")
    guide_manager = plugin_manager.get_plugin("guide_manager")

    # 保存当前状态
    mouse_manager.save_state({"guide": "test", "step": 3})

    # 暂停
    await mouse_manager.pause()
    assert await mouse_manager.is_paused() is True

    # 恢复
    await mouse_manager.resume()
    assert await mouse_manager.is_paused() is False

    # 检查状态保存
    state = mouse_manager.get_saved_state()
    assert state == {"guide": "test", "step": 3}
