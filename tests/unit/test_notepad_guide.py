"""记事本操作指南测试"""

import pytest
import pytest_asyncio
from plugins.guide_manager.plugin import GuideManagerPlugin


@pytest_asyncio.fixture
async def guide_manager():
    plugin = GuideManagerPlugin(guides_dir="D:/MI-Hands/app_guides")
    await plugin.initialize()
    return plugin


@pytest.mark.asyncio
async def test_notepad_guide_exists(guide_manager):
    """测试记事本操作指南存在"""
    guide = await guide_manager.get_guide("notepad")
    assert guide is not None
    assert guide.name == "记事本"


@pytest.mark.asyncio
async def test_notepad_operations(guide_manager):
    """测试记事本操作"""
    guide = await guide_manager.get_guide("notepad")
    assert "open" in guide.operations
    assert "type_text" in guide.operations
    assert "save" in guide.operations
