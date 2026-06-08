"""AppAgent 单元测试

测试执行层的核心功能：
- execute() 方法
- _execute_click()
- _execute_type_text()
- _execute_hotkey()
- 引擎选择和降级
- 统计记录
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.v3.core.app_agent import AppAgent
from src.v3.core.action_models import Action, ActionType, ActionResult


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def app_agent():
    """创建一个 AppAgent，预设 mock 引擎"""
    agent = AppAgent()
    agent._uia_engine = MagicMock()
    agent._pyautogui = MagicMock()
    return agent


# ============================================================
# execute() 方法测试
# ============================================================

class TestExecute:
    """测试 execute 主流程"""

    def test_execute_increments_total_actions(self, app_agent):
        """每次执行都增加 total_actions 计数"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent.execute(action)
        assert app_agent.stats["total_actions"] == 1

    def test_execute_records_action_type(self, app_agent):
        """记录操作类型"""
        action = Action(action_type=ActionType.CLICK, params={"index": 0})
        app_agent.execute(action)
        assert app_agent.stats["action_types"]["click"] == 1

    def test_execute_success_increments_success_count(self, app_agent):
        """成功操作增加 success_count"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        result = app_agent.execute(action)
        assert result.success is True
        assert app_agent.stats["success_count"] == 1
        assert app_agent.stats["failure_count"] == 0

    def test_execute_unsupported_action_type(self, app_agent):
        """不支持的操作类型返回失败"""
        action = Action(action_type=ActionType.SCREENSHOT, params={})
        result = app_agent.execute(action)
        assert result.success is False
        assert "不支持" in result.message

    def test_execute_exception_handling(self, app_agent):
        """异常时记录失败"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent._execute_wait = MagicMock(side_effect=Exception("test error"))
        result = app_agent.execute(action)
        assert result.success is False
        assert app_agent.stats["failure_count"] == 1
        assert app_agent.stats["error_types"]["other"] == 1

    def test_execute_updates_avg_duration(self, app_agent):
        """更新平均耗时"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent.execute(action)
        assert app_agent.stats["avg_duration"] >= 0


# ============================================================
# _execute_click 测试
# ============================================================

class TestExecuteClick:
    """测试点击操作"""

    def test_click_via_uia(self, app_agent):
        """通过 UIA 引擎点击"""
        app_agent._uia_engine.click_node.return_value = "已点击控件"
        action = Action(action_type=ActionType.CLICK, params={"index": 5})
        result = app_agent._execute_click(action, uia_tree=MagicMock())
        assert result.success is True
        assert "已点击" in result.message

    def test_click_uia_fails_fallback_to_coordinates(self, app_agent):
        """UIA 失败时降级到坐标点击"""
        app_agent._uia_engine.click_node.return_value = "点击失败"
        # 模拟有节点的 UIA 树
        mock_tree = MagicMock()
        mock_node = MagicMock()
        mock_node.rect = [100, 200, 300, 400]
        mock_tree.nodes = [mock_node]
        mock_tree.__len__ = MagicMock(return_value=1)
        mock_tree.__bool__ = MagicMock(return_value=True)

        action = Action(action_type=ActionType.CLICK, params={"index": 0})
        result = app_agent._execute_click(action, uia_tree=mock_tree)
        assert result.success is True
        assert "坐标" in result.message

    def test_click_no_uia_no_tree(self, app_agent):
        """无 UIA 引擎且无树时返回失败"""
        app_agent._uia_engine = None
        # Mock _ensure_uia 返回 None
        app_agent._ensure_uia = MagicMock(return_value=None)
        action = Action(action_type=ActionType.CLICK, params={"index": 0})
        result = app_agent._execute_click(action, uia_tree=None)
        assert result.success is False
        assert "无法定位" in result.message


# ============================================================
# _execute_type_text 测试
# ============================================================

class TestExecuteTypeText:
    """测试输入文字"""

    def test_type_text_via_uia(self, app_agent):
        """通过 UIA 输入文字"""
        app_agent._uia_engine.type_text.return_value = "输入成功"
        action = Action(action_type=ActionType.TYPE_TEXT, params={"text": "hello", "index": 2})
        result = app_agent._execute_type_text(action, uia_tree=None)
        assert result.success is True
        app_agent._uia_engine.type_text.assert_called_with("hello", 2)

    def test_type_text_fallback_clipboard(self, app_agent):
        """UIA 不可用时降级到剪贴板"""
        app_agent._uia_engine = None
        app_agent._ensure_uia = MagicMock(return_value=None)
        app_agent._pyautogui = MagicMock()

        action = Action(action_type=ActionType.TYPE_TEXT, params={"text": "test input"})
        with patch.dict("sys.modules", {"pyperclip": MagicMock()}):
            result = app_agent._execute_type_text(action, uia_tree=None)
        assert result.success is True
        assert "剪贴板" in result.message

    def test_type_text_no_engine(self, app_agent):
        """所有引擎都不可用时返回失败"""
        app_agent._uia_engine = None
        app_agent._ensure_uia = MagicMock(return_value=None)
        app_agent._pyautogui = None
        app_agent._ensure_pyautogui = MagicMock(return_value=None)
        action = Action(action_type=ActionType.TYPE_TEXT, params={"text": "hello"})
        result = app_agent._execute_type_text(action, uia_tree=None)
        assert result.success is False
        assert "输入失败" in result.message


# ============================================================
# _execute_hotkey 测试
# ============================================================

class TestExecuteHotkey:
    """测试组合键"""

    def test_hotkey_via_uia(self, app_agent):
        """通过 UIA 执行组合键"""
        app_agent._uia_engine.hotkey.return_value = "组合键执行成功"
        action = Action(action_type=ActionType.HOTKEY, params={"keys": ["ctrl", "s"]})
        result = app_agent._execute_hotkey(action)
        assert result.success is True
        app_agent._uia_engine.hotkey.assert_called_with(["ctrl", "s"])

    def test_hotkey_no_engine(self, app_agent):
        """无引擎时返回失败"""
        app_agent._uia_engine = None
        app_agent._ensure_uia = MagicMock(return_value=None)
        action = Action(action_type=ActionType.HOTKEY, params={"keys": ["ctrl", "s"]})
        result = app_agent._execute_hotkey(action)
        assert result.success is False
        assert "组合键失败" in result.message


# ============================================================
# _execute_wait 测试
# ============================================================

class TestExecuteWait:
    """测试等待操作"""

    def test_wait(self, app_agent):
        """等待指定秒数"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        with patch("src.v3.core.app_agent.time.sleep") as mock_sleep:
            result = app_agent._execute_wait(action)
        assert result.success is True
        mock_sleep.assert_called_with(0)


# ============================================================
# _execute_scroll 测试
# ============================================================

class TestExecuteScroll:
    """测试滚动操作"""

    def test_scroll_down(self, app_agent):
        """向下滚动"""
        action = Action(action_type=ActionType.SCROLL, params={"direction": "down"})
        result = app_agent._execute_scroll(action)
        assert result.success is True
        app_agent._pyautogui.scroll.assert_called_with(-3)

    def test_scroll_up(self, app_agent):
        """向上滚动"""
        action = Action(action_type=ActionType.SCROLL, params={"direction": "up"})
        result = app_agent._execute_scroll(action)
        assert result.success is True
        app_agent._pyautogui.scroll.assert_called_with(3)


# ============================================================
# 引擎选择和降级测试
# ============================================================

class TestEngineSelection:
    """测试引擎选择逻辑"""

    def test_ensure_uia_returns_cached(self, app_agent):
        """确保 UIA 引擎缓存复用"""
        engine = app_agent._ensure_uia()
        assert engine is app_agent._uia_engine

    def test_ensure_pyautogui_returns_cached(self, app_agent):
        """确保 pyautogui 缓存复用"""
        pg = app_agent._ensure_pyautogui()
        assert pg is app_agent._pyautogui

    def test_draw_path_engine_selection(self, app_agent):
        """绘制路径根据 engine 参数选择"""
        action = Action(
            action_type=ActionType.DRAW_PATH,
            params={"points": [[100, 100], [200, 200]], "engine": "pyautogui", "speed": 0}
        )
        result = app_agent._execute_draw_path(action)
        assert result.success is True
        assert "pyautogui" in result.message

    def test_draw_path_insufficient_points(self, app_agent):
        """点数不足返回失败"""
        action = Action(
            action_type=ActionType.DRAW_PATH,
            params={"points": [[100, 100]], "engine": "pyautogui"}
        )
        result = app_agent._execute_draw_path(action)
        assert result.success is False
        assert "2 个点" in result.message

    def test_draw_precise_forces_win32(self, app_agent):
        """精细绘制强制使用 Win32"""
        captured_params = {}

        def capture_draw(action):
            captured_params.update(action.params)
            return ActionResult(action=action, success=True, message="ok")

        app_agent._execute_draw_path = capture_draw
        action = Action(
            action_type=ActionType.DRAW_PRECISE,
            params={"points": [[0, 0], [100, 100]], "engine": "pyautogui"}
        )
        app_agent._execute_draw_precise(action)
        assert captured_params.get("engine") == "win32"

    def test_draw_path_empty_points(self, app_agent):
        """空点列表返回失败"""
        action = Action(
            action_type=ActionType.DRAW_PATH,
            params={"points": [], "engine": "pyautogui"}
        )
        result = app_agent._execute_draw_path(action)
        assert result.success is False


# ============================================================
# 统计记录测试
# ============================================================

class TestStats:
    """测试统计系统"""

    def test_initial_stats(self):
        """初始统计为零"""
        agent = AppAgent()
        stats = agent.stats
        assert stats["total_actions"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["avg_duration"] == 0

    def test_get_stats(self, app_agent):
        """获取统计信息"""
        stats = app_agent.get_stats()
        assert "total_actions" in stats
        assert "success_rate" in stats
        assert "engine_stats" in stats
        assert "error_types" in stats
        assert "action_types" in stats

    def test_success_rate(self, app_agent):
        """成功率计算"""
        for _ in range(2):
            action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
            app_agent.execute(action)
        stats = app_agent.get_stats()
        assert stats["success_rate"] == 1.0

    def test_reset_stats(self, app_agent):
        """重置统计"""
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent.execute(action)
        assert app_agent.stats["total_actions"] == 1

        app_agent.reset_stats()
        assert app_agent.stats["total_actions"] == 0
        assert app_agent.stats["success_count"] == 0

    def test_classify_error(self, app_agent):
        """错误分类"""
        assert app_agent._classify_error("connection timeout") == "timeout"
        assert app_agent._classify_error("Access Denied") == "permission"
        assert app_agent._classify_error("element not found") == "not_found"
        assert app_agent._classify_error("network error") == "network"
        assert app_agent._classify_error("control failed") == "ui_error"
        assert app_agent._classify_error("ImportError: no module") == "import_error"
        assert app_agent._classify_error("something random") == "other"

    def test_error_types_recorded(self, app_agent):
        """错误类型被正确记录"""
        app_agent._execute_wait = MagicMock(side_effect=Exception("connection refused"))
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent.execute(action)
        assert app_agent.stats["failure_count"] == 1
        # "connection refused" -> 包含 "connection" -> "network"
        assert app_agent.stats["error_types"].get("network", 0) == 1

    def test_timeout_error_classification(self, app_agent):
        """超时错误分类"""
        app_agent._execute_wait = MagicMock(side_effect=Exception("request timed out"))
        action = Action(action_type=ActionType.WAIT, params={"seconds": 0})
        app_agent.execute(action)
        assert app_agent.stats["error_types"].get("timeout", 0) == 1

    def test_multiple_action_types_recorded(self, app_agent):
        """多种操作类型被记录"""
        actions = [
            Action(action_type=ActionType.CLICK, params={"index": 0}),
            Action(action_type=ActionType.CLICK, params={"index": 1}),
            Action(action_type=ActionType.WAIT, params={"seconds": 0}),
        ]
        for a in actions:
            app_agent.execute(a)
        assert app_agent.stats["action_types"]["click"] == 2
        assert app_agent.stats["action_types"]["wait"] == 1
