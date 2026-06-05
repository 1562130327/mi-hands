"""GitHub 同步插件测试"""

import pytest
import pytest_asyncio
import tempfile
import os
from plugins.github_sync.plugin import GitHubSyncPlugin


@pytest.fixture
def github_sync():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = GitHubSyncPlugin(local_dir=tmpdir)
        yield plugin


@pytest.mark.asyncio
async def test_initialization(github_sync):
    """测试初始化"""
    result = await github_sync.initialize()
    assert result is True
    assert github_sync._initialized is True


@pytest.mark.asyncio
async def test_get_status(github_sync):
    """测试获取状态"""
    await github_sync.initialize()
    status = await github_sync.get_status()

    assert status["name"] == "github_sync"
    assert status["version"] == "1.0.0"
    assert status["initialized"] is True


@pytest.mark.asyncio
async def test_validate_guide_valid(github_sync):
    """测试验证有效指南"""
    guide_content = """
metadata:
  name: 测试应用
  version: "1.0.0"
identity:
  process_name: test.exe
operations:
  open:
    description: 打开应用
    steps:
      - action: click
        target: "图标"
"""
    result = await github_sync.validate_guide(guide_content)
    assert result["valid"] is True
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_validate_guide_invalid(github_sync):
    """测试验证无效指南"""
    guide_content = """
metadata:
  version: "1.0.0"
"""
    result = await github_sync.validate_guide(guide_content)
    assert result["valid"] is False
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_anonymize(github_sync):
    """测试匿名化"""
    content = r"C:\Users\Administrator\test"
    result = github_sync._anonymize(content)
    assert "Administrator" not in result
    assert "User" in result
