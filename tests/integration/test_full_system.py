"""完整系统集成测试"""

import pytest
import pytest_asyncio
import tempfile
from core.plugin_manager import PluginManager
from core.event_system import EventBus
from plugins.wait.plugin import WaitPlugin
from plugins.mouse_manager.plugin import MouseManagerPlugin
from plugins.guide_manager.plugin import GuideManagerPlugin


@pytest_asyncio.fixture
async def full_system():
    """创建完整系统"""
    with tempfile.TemporaryDirectory() as tmpdir:
        event_bus = EventBus()
        plugin_manager = PluginManager(event_bus)

        # 注册所有插件
        await plugin_manager.register(WaitPlugin())
        await plugin_manager.register(MouseManagerPlugin())
        await plugin_manager.register(GuideManagerPlugin(guides_dir=tmpdir))

        yield plugin_manager


@pytest.mark.asyncio
async def test_full_workflow(full_system):
    """测试完整工作流"""
    pm = full_system

    # 1. 获取插件
    wait = pm.get_plugin("wait")
    mouse = pm.get_plugin("mouse_manager")
    guide_mgr = pm.get_plugin("guide_manager")

    # 2. 测试等待功能
    wait._get_uia_tree = lambda: {"key": "value"}
    stable = await wait.wait_for_stable(timeout=1)
    assert stable is True

    # 3. 测试鼠标管理
    await mouse.pause()
    assert await mouse.is_paused() is True

    mouse.save_state({"test": True})
    state = mouse.get_saved_state()
    assert state == {"test": True}

    await mouse.resume()
    assert await mouse.is_paused() is False

    # 4. 测试操作指南
    from plugins.guide_manager.models import AppGuide
    guide = AppGuide(name="测试", version="1.0.0", process_name="test.exe")
    await guide_mgr.save_guide("test", guide)

    result = await guide_mgr.get_guide("test")
    assert result.name == "测试"
