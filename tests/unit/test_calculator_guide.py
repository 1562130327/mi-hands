"""计算器操作指南测试"""

import pytest
import pytest_asyncio
from plugins.guide_manager.plugin import GuideManagerPlugin


@pytest_asyncio.fixture
async def guide_manager():
    plugin = GuideManagerPlugin(guides_dir="D:/MI-Hands/app_guides")
    await plugin.initialize()
    return plugin


@pytest.mark.asyncio
async def test_calculator_guide_exists(guide_manager):
    """测试计算器操作指南存在"""
    guide = await guide_manager.get_guide("calculator")
    assert guide is not None
    assert guide.name == "计算器"


@pytest.mark.asyncio
async def test_calculator_operations(guide_manager):
    """测试计算器操作"""
    guide = await guide_manager.get_guide("calculator")
    assert "open" in guide.operations
    assert "calculate" in guide.operations
