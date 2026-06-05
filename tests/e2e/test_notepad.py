"""记事本端到端测试"""

import pytest
import pytest_asyncio
import asyncio
from core.plugin_manager import PluginManager
from plugins.wait.plugin import WaitPlugin
from plugins.guide_manager.plugin import GuideManagerPlugin
from plugins.guide_manager.models import AppGuide


@pytest_asyncio.fixture
async def mi_hands():
    """创建 MI Hands 实例"""
    plugin_manager = PluginManager()
    await plugin_manager.register(WaitPlugin())
    await plugin_manager.register(GuideManagerPlugin(guides_dir="D:/MI-Hands/app_guides"))
    return plugin_manager


@pytest.mark.asyncio
async def test_notepad_workflow(mi_hands):
    """测试记事本完整工作流"""
    guide_manager = mi_hands.get_plugin("guide_manager")
    wait_plugin = mi_hands.get_plugin("wait")

    # 获取记事本操作指南
    guide = await guide_manager.get_guide("notepad")
    assert guide is not None

    # 验证操作存在
    assert "open" in guide.operations
    assert "type_text" in guide.operations
    assert "save" in guide.operations

    # 注意：实际执行需要人工干预，因为涉及真实应用
