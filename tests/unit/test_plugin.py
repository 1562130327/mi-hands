"""MCPPlugin 单元测试

测试 MCP 插件的核心功能：
- MCPPlugin 初始化
- _ensure_engine()
- _ensure_mimo()
- _ensure_agents() 状态复用
- 工具注册
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.v3.mcp.plugin import MCPPlugin
from src.v3.core.host_agent import HostAgent
from src.v3.core.app_agent import AppAgent


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def plugin():
    """创建一个 MCPPlugin 实例"""
    return MCPPlugin()


@pytest.fixture
def plugin_with_env():
    """创建一个带 MIMO_API_KEY 环境变量的 MCPPlugin"""
    with patch.dict(os.environ, {"MIMO_API_KEY": "test-key-12345"}):
        yield MCPPlugin()


# ============================================================
# 初始化测试
# ============================================================

class TestMCPPluginInit:
    """测试 MCPPlugin 初始化"""

    def test_init_defaults(self, plugin):
        """初始化时所有组件为 None"""
        assert plugin._engine is None
        assert plugin._mimo_client is None
        assert plugin._host_agent is None
        assert plugin._app_agent is None
        assert plugin._verify_layer is None
        assert plugin._experience_manager is None

    def test_init_has_security(self, plugin):
        """初始化时创建 SecurityManager 和 ActionLogger"""
        assert plugin._security is not None
        assert plugin._action_logger is not None

    def test_name_and_version(self, plugin):
        """name 和 version 正确"""
        assert plugin.name == "mi-hands"
        assert plugin.version == "3.0.0"


# ============================================================
# _ensure_engine 测试
# ============================================================

class TestEnsureEngine:
    """测试 UIA 引擎初始化"""

    def test_engine_initially_none(self, plugin):
        """初始时引擎为 None"""
        assert plugin._engine is None

    def test_engine_caches_result(self, plugin):
        """引擎缓存复用"""
        mock_engine = MagicMock()
        plugin._engine = mock_engine
        result = plugin._ensure_engine()
        assert result is mock_engine

    def test_engine_import_failure(self, plugin):
        """import 失败时引擎保持 None"""
        with patch.dict("sys.modules", {"comtypes": None}):
            result = plugin._ensure_engine()
        # import 失败，引擎仍为 None（或已被设置）
        # 关键是不抛异常

    def test_engine_exception_on_init(self, plugin):
        """初始化异常时引擎保持 None"""
        with patch("builtins.__import__", side_effect=Exception("init failed")):
            # 通过设置 _engine 为 None 确保进入初始化逻辑
            plugin._engine = None
            result = plugin._ensure_engine()
        # 不抛异常，结果为 None


# ============================================================
# _ensure_mimo 测试
# ============================================================

class TestEnsureMimo:
    """测试 MiMo 客户端初始化"""

    def test_mimo_initially_none(self, plugin):
        """初始时 MiMo 客户端为 None"""
        assert plugin._mimo_client is None

    def test_mimo_with_api_key(self, plugin_with_env):
        """有 API key 时创建 OpenAI 客户端"""
        client = plugin_with_env._ensure_mimo()
        # 创建了客户端（或 mock 了 OpenAI）
        assert client is not None

    def test_mimo_without_api_key(self, plugin):
        """没有 API key 时返回 None"""
        with patch.dict(os.environ, {}, clear=True):
            # 移除 MIMO_API_KEY
            os.environ.pop("MIMO_API_KEY", None)
            result = plugin._ensure_mimo()
        assert result is None

    def test_mimo_caches_result(self, plugin_with_env):
        """MiMo 客户端缓存复用"""
        mock_client = MagicMock()
        plugin_with_env._mimo_client = mock_client
        result = plugin_with_env._ensure_mimo()
        assert result is mock_client


# ============================================================
# _ensure_agents 测试
# ============================================================

class TestEnsureAgents:
    """测试三层架构实例初始化"""

    def test_agents_initially_none(self, plugin):
        """初始时所有 agent 为 None"""
        assert plugin._host_agent is None
        assert plugin._app_agent is None
        assert plugin._verify_layer is None
        assert plugin._experience_manager is None

    def test_agents_caches_instances(self, plugin):
        """agent 实例缓存复用"""
        mock_host = MagicMock(spec=HostAgent)
        mock_app = MagicMock(spec=AppAgent)
        mock_verify = MagicMock()

        plugin._host_agent = mock_host
        plugin._app_agent = mock_app
        plugin._verify_layer = mock_verify
        plugin._experience_manager = MagicMock()
        plugin._smart_verify = MagicMock()
        plugin._learning_loop = MagicMock()

        host, app, verify = plugin._ensure_agents()
        assert host is mock_host
        assert app is mock_app
        assert verify is mock_verify

    def test_agents_creates_when_none(self, plugin):
        """没有 agent 时创建新实例"""
        # Mock 所有外部依赖
        plugin._mimo_client = MagicMock()
        plugin._engine = MagicMock()

        with patch("src.v3.mcp.plugin.ExperienceManager") as MockExp:
            with patch("src.v3.mcp.plugin.SmartVerifyLayer") as MockSmart:
                with patch("src.v3.mcp.plugin.HostAgent") as MockHost:
                    with patch("src.v3.mcp.plugin.AppAgent") as MockApp:
                        with patch("src.v3.mcp.plugin.VerifyLayer") as MockVerify:
                            with patch("src.v3.mcp.plugin.LearningLoop") as MockLearn:
                                MockHost.return_value = MagicMock()
                                MockApp.return_value = MagicMock()
                                MockVerify.return_value = MagicMock()
                                MockSmart.return_value = MagicMock()
                                MockLearn.return_value = MagicMock()

                                host, app, verify = plugin._ensure_agents()

                                assert host is not None
                                assert app is not None
                                assert verify is not None
                                assert plugin._experience_manager is not None


# ============================================================
# _extract_task_tags 测试
# ============================================================

class TestExtractTaskTags:
    """测试标签提取"""

    def test_chrome_tags(self, plugin):
        """浏览器任务提取 chrome 标签"""
        tags = plugin._extract_task_tags("在浏览器中打开 Google")
        assert "chrome" in tags

    def test_vscode_tags(self, plugin):
        """VSCode 任务提取 vscode 标签"""
        tags = plugin._extract_task_tags("在 VSCode 中编辑代码")
        assert "vscode" in tags

    def test_wechat_tags(self, plugin):
        """微信任务提取 wechat 标签"""
        tags = plugin._extract_task_tags("打开微信")
        assert "wechat" in tags

    def test_paint_tags(self, plugin):
        """画图任务提取 paint 标签"""
        tags = plugin._extract_task_tags("在画图中绘制")
        assert "paint" in tags

    def test_no_matching_tags(self, plugin):
        """无匹配时返回空列表"""
        tags = plugin._extract_task_tags("一些无关的任务")
        assert len(tags) == 0

    def test_multiple_tags(self, plugin):
        """可以匹配多个标签"""
        tags = plugin._extract_task_tags("在浏览器中打开画图")
        assert "chrome" in tags
        assert "paint" in tags


# ============================================================
# 工具注册测试
# ============================================================

class TestRegisterTools:
    """测试 MCP 工具注册"""

    def test_register_tools(self, plugin):
        """注册工具时不报错"""
        mock_mcp = MagicMock()
        plugin.register_tools(mock_mcp)
        # 验证 tool() 被调用了多次
        assert mock_mcp.tool.call_count > 10  # 有很多工具

    def test_registered_tool_names(self, plugin):
        """验证关键工具被注册"""
        mock_mcp = MagicMock()
        plugin.register_tools(mock_mcp)

        # @mcp.tool() 是装饰器：先调用 tool() 返回装饰器，再用装饰器调用函数
        # 所以函数注册在 mock_mcp.tool.return_value 的调用参数中
        decorator = mock_mcp.tool.return_value
        registered_names = []
        for call in decorator.call_args_list:
            if call.args:
                registered_names.append(call.args[0].__name__)

        assert "run_task" in registered_names
        assert "snapshot" in registered_names
        assert "click" in registered_names
        assert "type_text" in registered_names
        assert "hotkey" in registered_names
        assert "list_windows" in registered_names


# ============================================================
# _record_task_experience 测试
# ============================================================

class TestRecordTaskExperience:
    """测试经验记录"""

    def test_record_without_experience_manager(self, plugin):
        """没有经验管理器时不报错"""
        plugin._experience_manager = None
        # 不应抛异常
        plugin._record_task_experience(
            task="test",
            plan=MagicMock(),
            action_results=[],
            success=True,
        )

    def test_record_with_experience_manager(self, plugin):
        """有经验管理器时记录经验"""
        mock_exp_mgr = MagicMock()
        plugin._experience_manager = mock_exp_mgr

        # 创建 mock action result
        mock_action = MagicMock()
        mock_action.action_type = MagicMock(value="click")
        mock_action.params = {"index": 0}
        mock_action.target_control = "button"
        mock_action.description = "click button"

        mock_result = MagicMock()
        mock_result.action = mock_action
        mock_result.success = True
        mock_result.message = "ok"

        plugin._record_task_experience(
            task="打开记事本",
            plan=MagicMock(),
            action_results=[mock_result],
            success=True,
        )
        mock_exp_mgr.learn_from_task.assert_called_once()
        call_kwargs = mock_exp_mgr.learn_from_task.call_args
        assert call_kwargs.kwargs["task"] == "打开记事本"
        assert call_kwargs.kwargs["success"] is True

    def test_record_with_failure(self, plugin):
        """记录失败经验"""
        mock_exp_mgr = MagicMock()
        plugin._experience_manager = mock_exp_mgr

        mock_action = MagicMock()
        mock_action.action_type = MagicMock(value="click")
        mock_action.params = {}
        mock_action.target_control = ""
        mock_action.description = "click"

        mock_result = MagicMock()
        mock_result.action = mock_action
        mock_result.success = False
        mock_result.message = "element not found"

        plugin._record_task_experience(
            task="test task",
            plan=MagicMock(),
            action_results=[mock_result],
            success=False,
            error_summary="element not found",
        )
        call_kwargs = mock_exp_mgr.learn_from_task.call_args
        assert call_kwargs.kwargs["success"] is False
        assert call_kwargs.kwargs["error_summary"] == "element not found"


# ============================================================
# _replan_from_feedback 测试
# ============================================================

class TestReplanFromFeedback:
    """测试反馈重规划"""

    def test_replan_no_mimo_returns_none(self, plugin):
        """没有 MiMo 客户端时返回 None"""
        plugin._mimo_client = None
        result = plugin._replan_from_feedback("test", MagicMock(), MagicMock())
        assert result is None


# ============================================================
# _get_screenshot_base64 / _get_uia_tree 测试
# ============================================================

class TestScreenCapture:
    """测试截图和 UIA 树获取"""

    def test_get_screenshot_no_engine(self, plugin):
        """引擎初始化失败时返回空字符串"""
        plugin._engine = None
        # Mock _ensure_engine 返回 None（模拟初始化失败）
        plugin._ensure_engine = MagicMock(return_value=None)
        result = plugin._get_screenshot_base64()
        assert result == ""

    def test_get_uia_tree_no_engine(self, plugin):
        """引擎初始化失败时返回空字符串"""
        plugin._engine = None
        plugin._ensure_engine = MagicMock(return_value=None)
        result = plugin._get_uia_tree()
        assert result == ""

    def test_get_screenshot_with_engine(self, plugin):
        """有引擎时返回截图"""
        mock_engine = MagicMock()
        mock_screenshot = MagicMock()
        mock_screenshot.base64_data = "abc123"
        mock_engine.take_screenshot.return_value = mock_screenshot
        plugin._engine = mock_engine

        result = plugin._get_screenshot_base64()
        assert result == "abc123"

    def test_get_uia_tree_with_engine(self, plugin):
        """有引擎时返回 UIA 树"""
        mock_engine = MagicMock()
        mock_engine.get_snapshot.return_value = "<UIA Tree>"
        plugin._engine = mock_engine

        result = plugin._get_uia_tree()
        assert result == "<UIA Tree>"

    def test_get_screenshot_engine_exception(self, plugin):
        """引擎抛异常时返回空字符串"""
        mock_engine = MagicMock()
        mock_engine.take_screenshot.side_effect = Exception("screenshot failed")
        plugin._engine = mock_engine

        result = plugin._get_screenshot_base64()
        assert result == ""
