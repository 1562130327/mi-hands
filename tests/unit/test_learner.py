"""学习引擎测试"""

import pytest
import pytest_asyncio
import tempfile
import os
from plugins.guide_manager.learner import Learner


@pytest.fixture
def learner():
    return Learner()


@pytest.mark.asyncio
async def test_learn_app(learner):
    """测试学习应用"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        readme_path = os.path.join(tmpdir, "README.txt")
        with open(readme_path, "w") as f:
            f.write("TestApp v1.0.0\nA test application")

        # 学习应用
        guide = await learner.learn_app(tmpdir)

        assert guide is not None
        assert guide.name == "TestApp v1.0.0"  # 从 README 提取
        assert "open" in guide.operations


@pytest.mark.asyncio
async def test_learn_from_uia(learner):
    """测试从 UIA 树学习"""
    uia_tree = {
        "type": "WindowControl",
        "name": "Test Window",
        "children": [
            {"type": "ButtonControl", "name": "OK", "children": []},
            {"type": "EditControl", "name": "Input", "children": []}
        ]
    }

    result = await learner.learn_from_uia("test", uia_tree)

    assert len(result["buttons"]) == 1
    assert result["buttons"][0]["name"] == "OK"
    assert len(result["inputs"]) == 1
    assert result["inputs"][0]["name"] == "Input"


@pytest.mark.asyncio
async def test_merge_learned_info(learner):
    """测试合并学习信息"""
    local_info = {
        "name": "TestApp",
        "version": "1.0.0",
        "process_name": "test.exe"
    }

    uia_info = {
        "buttons": [{"name": "OK", "path": [0, 0]}],
        "inputs": [{"name": "Input", "path": [0, 1]}],
        "menus": []
    }

    web_info = {}

    merged = learner.merge_learned_info(local_info, uia_info, web_info)

    assert merged["name"] == "TestApp"
    assert "click_ok" in merged["operations"]
