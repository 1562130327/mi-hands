"""
VerifyLayer 单元测试
"""

import pytest
import comtypes
comtypes.CoInitialize()

from src.v3.core.verify import VerifyLayer
from src.v3.core.action_models import TaskPlan


class TestVerifyLayer:
    """VerifyLayer 测试"""

    def test_init(self):
        """测试初始化"""
        vl = VerifyLayer()
        assert vl.mimo is None
        assert vl.vision is None

    def test_init_with_clients(self):
        """测试带参数初始化"""
        vl = VerifyLayer(mimo_client="mock", vision_engine="mock")
        assert vl.mimo == "mock"
        assert vl.vision == "mock"

    def test_verify_no_mimo(self):
        """测试无 MiMo 时的验证"""
        vl = VerifyLayer()
        plan = TaskPlan(goal="test task")
        result = vl.verify("test task", plan, max_retries=1)
        assert result.success is False
        assert result.retries == 1

    def test_judge_fallback_completed(self):
        """测试降级判断 - 完成"""
        vl = VerifyLayer()
        judgment = vl._judge_fallback("test", "some ui tree content")
        assert judgment["completed"] is True

    def test_judge_fallback_not_completed(self):
        """测试降级判断 - 未完成"""
        vl = VerifyLayer()
        judgment = vl._judge_fallback("test", "无法获取")
        assert judgment["completed"] is False

    def test_take_screenshot_no_vision(self):
        """测试无视觉引擎时的截图"""
        vl = VerifyLayer()
        screenshot = vl._take_screenshot()
        assert screenshot == ""

    def test_get_uia_tree_no_vision(self):
        """测试无视觉引擎时获取 UIA 树"""
        vl = VerifyLayer()
        tree = vl._get_uia_tree()
        assert tree == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
