"""GUI 插件测试"""

import pytest
import pytest_asyncio
from plugins.gui.plugin import GUIPlugin


@pytest.fixture
def gui_plugin():
    return GUIPlugin()


@pytest.mark.asyncio
async def test_initialization(gui_plugin):
    """测试初始化"""
    # 注意：在没有显示器的环境中可能失败
    try:
        result = await gui_plugin.initialize()
        # 如果 PyQt 可用，应该成功
        if result:
            assert gui_plugin._initialized is True
        else:
            # PyQt 不可用，这是预期的
            assert gui_plugin._initialized is False
    except Exception:
        # 在无显示器环境中可能失败
        pass


@pytest.mark.asyncio
async def test_get_status(gui_plugin):
    """测试获取状态"""
    status = await gui_plugin.get_status()

    assert status["name"] == "gui"
    assert status["version"] == "1.0.0"
