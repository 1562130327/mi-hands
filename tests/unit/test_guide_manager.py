"""操作指南管理插件测试"""

import pytest
import tempfile
import os
from plugins.guide_manager.plugin import GuideManagerPlugin
from plugins.guide_manager.models import AppGuide


@pytest.fixture
def guide_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = GuideManagerPlugin(guides_dir=tmpdir)
        yield plugin


@pytest.mark.asyncio
async def test_save_and_get_guide(guide_manager):
    """测试保存和获取操作指南"""
    guide = AppGuide(
        name="测试应用",
        version="1.0.0",
        process_name="test.exe"
    )

    await guide_manager.save_guide("test_app", guide)
    result = await guide_manager.get_guide("test_app")

    assert result is not None
    assert result.name == "测试应用"


@pytest.mark.asyncio
async def test_list_guides(guide_manager):
    """测试列出所有操作指南"""
    guide1 = AppGuide(name="应用1", version="1.0.0", process_name="app1.exe")
    guide2 = AppGuide(name="应用2", version="1.0.0", process_name="app2.exe")

    await guide_manager.save_guide("app1", guide1)
    await guide_manager.save_guide("app2", guide2)

    guides = await guide_manager.list_guides()
    assert len(guides) == 2
    assert "app1" in guides
    assert "app2" in guides
