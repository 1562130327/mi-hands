"""等待插件测试"""

import pytest
import asyncio
from plugins.wait.plugin import WaitPlugin


@pytest.fixture
def wait_plugin():
    return WaitPlugin()


@pytest.mark.asyncio
async def test_wait_for_stable(wait_plugin):
    """测试等待 UI 稳定"""
    # 模拟 UI 稳定
    wait_plugin._get_uia_tree = lambda: {"key": "value"}

    result = await wait_plugin.wait_for_stable(timeout=1)
    assert result is True


@pytest.mark.asyncio
async def test_wait_timeout(wait_plugin):
    """测试超时"""
    # 模拟 UI 一直变化
    counter = [0]
    def changing_tree():
        counter[0] += 1
        return {"key": counter[0]}

    wait_plugin._get_uia_tree = changing_tree

    result = await wait_plugin.wait_for_stable(timeout=1)
    assert result is False
