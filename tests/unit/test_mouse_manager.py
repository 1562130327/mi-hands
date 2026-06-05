"""鼠标管理插件测试"""

import pytest
from plugins.mouse_manager.plugin import MouseManagerPlugin


@pytest.fixture
def mouse_manager():
    return MouseManagerPlugin()


@pytest.mark.asyncio
async def test_pause_resume(mouse_manager):
    """测试暂停和继续"""
    assert await mouse_manager.is_paused() is False

    await mouse_manager.pause()
    assert await mouse_manager.is_paused() is True

    await mouse_manager.resume()
    assert await mouse_manager.is_paused() is False


@pytest.mark.asyncio
async def test_save_restore_state(mouse_manager):
    """测试保存和恢复状态"""
    mouse_manager.save_state({"step": 3, "action": "click"})

    state = mouse_manager.get_saved_state()
    assert state == {"step": 3, "action": "click"}
