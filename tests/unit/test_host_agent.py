"""HostAgent 单元测试

测试决策层的核心功能：
- plan() 方法
- _build_planning_prompt()
- _parse_response()
- _extract_json()
- 经验集成（搜索经验、复用经验）
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.v3.core.host_agent import HostAgent
from src.v3.core.action_models import Action, ActionType, TaskPlan
from src.v3.core.state_manager import StateManager
from src.v3.core.experience_manager import Experience, ExperienceManager, StepRecord


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def host_agent():
    """创建一个不带 MiMo 客户端、有干净经验管理器的 HostAgent"""
    exp_mgr = ExperienceManager(state_manager=None)
    exp_mgr._experiences.clear()
    exp_mgr._index.clear()
    return HostAgent(mimo_client=None, experience_manager=exp_mgr)


@pytest.fixture
def host_agent_with_mimo():
    """创建一个带 mock MiMo 客户端的 HostAgent"""
    mock_mimo = MagicMock()
    return HostAgent(mimo_client=mock_mimo, experience_manager=None)


@pytest.fixture
def host_agent_with_experience(tmp_path):
    """创建一个带经验管理器的 HostAgent（使用空实例避免测试间干扰）"""
    sm = StateManager(db_path=str(tmp_path / "test.db"))
    exp_mgr = ExperienceManager(state_manager=sm)
    return HostAgent(mimo_client=None, experience_manager=exp_mgr)


# ============================================================
# _extract_json 测试
# ============================================================

class TestExtractJson:
    """测试 JSON 提取逻辑"""

    def test_pure_json(self, host_agent):
        """纯 JSON 字符串直接返回"""
        text = '{"analysis": "ok", "steps": []}'
        result = host_agent._extract_json(text)
        parsed = json.loads(result)
        assert parsed["analysis"] == "ok"

    def test_markdown_json_block(self, host_agent):
        """从 ```json ... ``` 代码块中提取"""
        text = '''这是分析结果：
```json
{"analysis": "ok", "steps": [{"action": "click"}]}
```
以上是计划。'''
        result = host_agent._extract_json(text)
        parsed = json.loads(result)
        assert parsed["analysis"] == "ok"
        assert len(parsed["steps"]) == 1

    def test_plain_code_block(self, host_agent):
        """从普通 ``` ... ``` 代码块中提取"""
        text = '''```
{"analysis": "test", "steps": []}
```'''
        result = host_agent._extract_json(text)
        parsed = json.loads(result)
        assert parsed["analysis"] == "test"

    def test_thinking_before_json(self, host_agent):
        """MiMo 思考过程在 JSON 前面 — 简单 JSON（无嵌套列表）"""
        text = '''让我分析一下这个界面。首先看到的是一个按钮...
好的，这是我的规划：
{"analysis": "界面有一个确定按钮", "selected_scheme": "A", "requires_screenshot": true}'''
        result = host_agent._extract_json(text)
        parsed = json.loads(result)
        assert parsed["analysis"] == "界面有一个确定按钮"

    def test_empty_string(self, host_agent):
        """空字符串返回空"""
        result = host_agent._extract_json("")
        assert result == ""

    def test_none_returns_empty(self, host_agent):
        """None 返回空"""
        result = host_agent._extract_json(None)
        assert result == ""

    def test_no_json_in_text(self, host_agent):
        """文本中没有 JSON 返回空"""
        result = host_agent._extract_json("这里没有任何 JSON 内容")
        assert result == ""

    def test_nested_json_via_last_brace(self, host_agent):
        """嵌套 JSON 通过最后一个 { ... } 块提取"""
        text = '''分析结果如下：
一些思考过程...
{"analysis": "嵌套结构", "requires_screenshot": true}'''
        result = host_agent._extract_json(text)
        parsed = json.loads(result)
        assert parsed["analysis"] == "嵌套结构"


# ============================================================
# _build_planning_prompt 测试
# ============================================================

class TestBuildPlanningPrompt:
    """测试 prompt 构建"""

    def test_basic_prompt(self, host_agent):
        """基本 prompt 包含任务和 UIA 树"""
        prompt = host_agent._build_planning_prompt("打开记事本", "<UIA Tree>")
        assert "打开记事本" in prompt
        assert "<UIA Tree>" in prompt
        assert "MI Hands" in prompt

    def test_skill_injection(self, host_agent):
        """包含 skill 信息时注入到 prompt"""
        skills = [
            {"name": "notepad-skill", "prompt": "打开记事本的步骤...", "description": "记事本操作"}
        ]
        prompt = host_agent._build_planning_prompt("打开记事本", "<UIA>", matching_skills=skills)
        assert "notepad-skill" in prompt
        assert "可用 Skills" in prompt

    def test_multiple_skills_limit(self, host_agent):
        """最多注入 3 个 skill"""
        skills = [
            {"name": f"skill-{i}", "prompt": f"prompt-{i}", "description": f"desc-{i}"}
            for i in range(5)
        ]
        prompt = host_agent._build_planning_prompt("test", "<UIA>", matching_skills=skills)
        # 只有前 3 个
        assert "skill-0" in prompt
        assert "skill-2" in prompt
        assert "skill-3" not in prompt

    def test_experience_advice_injection(self, host_agent):
        """经验建议注入到 prompt"""
        advice = "## 操作经验参考\n- 上次打开成功了"
        prompt = host_agent._build_planning_prompt("打开应用", "<UIA>", experience_advice=advice)
        assert "操作经验参考" in prompt
        assert "上次打开成功了" in prompt

    def test_no_skills_no_advice(self, host_agent):
        """无 skill 无经验时 prompt 也正常"""
        prompt = host_agent._build_planning_prompt("点击按钮", "<UIA>")
        assert "可用操作" in prompt
        assert "draw_path" in prompt


# ============================================================
# _parse_response 测试
# ============================================================

class TestParseResponse:
    """测试响应解析"""

    def test_parse_valid_json(self, host_agent):
        """解析有效的 JSON 响应"""
        response = json.dumps({
            "analysis": "找到确定按钮",
            "steps": [
                {"action": "click", "index": 5, "engine": "pyautogui", "description": "点击确定"},
                {"action": "wait", "seconds": 1, "description": "等待"},
            ],
            "requires_screenshot": True
        })
        plan = host_agent._parse_response("点击确定", response)
        assert plan.goal == "点击确定"
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == ActionType.CLICK
        assert plan.steps[0].params["index"] == 5
        assert plan.steps[1].action_type == ActionType.WAIT
        assert plan.requires_screenshot is True

    def test_parse_invalid_json(self, host_agent):
        """无效 JSON 返回空 plan"""
        plan = host_agent._parse_response("test", "not json at all")
        assert plan.goal == "test"
        assert len(plan.steps) == 0

    def test_parse_with_markdown_block(self, host_agent):
        """从 markdown 代码块提取 JSON"""
        response = '''```json
{"analysis": "ok", "steps": [{"action": "hotkey", "keys": ["ctrl", "s"]}], "requires_screenshot": false}
```'''
        plan = host_agent._parse_response("保存文件", response)
        assert len(plan.steps) == 1
        assert plan.steps[0].action_type == ActionType.HOTKEY
        assert plan.requires_screenshot is False

    def test_parse_skips_invalid_steps(self, host_agent):
        """跳过无效步骤"""
        response = json.dumps({
            "analysis": "ok",
            "steps": [
                {"action": "click", "index": 0},
                {"action": "invalid_action_xyz"},  # 无效类型
                {"action": "wait", "seconds": 1},
            ],
        })
        plan = host_agent._parse_response("test", response)
        assert len(plan.steps) == 2  # 无效的被跳过

    def test_parse_empty_steps(self, host_agent):
        """空步骤列表"""
        response = json.dumps({"analysis": "没有步骤", "steps": []})
        plan = host_agent._parse_response("test", response)
        assert len(plan.steps) == 0


# ============================================================
# 经验集成测试
# ============================================================

class TestExperienceIntegration:
    """测试经验搜索和复用"""

    def test_find_reusable_experience_returns_none_when_no_manager(self, host_agent):
        """没有经验管理器时返回 None"""
        result = host_agent._find_reusable_experience("打开记事本")
        assert result is None

    def test_find_reusable_experience_returns_best(self, host_agent_with_experience):
        """能从经验管理器中找到最佳匹配"""
        exp_mgr = host_agent_with_experience.experience
        # 先记录一条成功经验
        exp_mgr.record_success(
            task="打开记事本",
            steps=[
                {"action_type": "hotkey", "params": {"keys": ["win", "r"]}, "description": "打开 Run"},
                {"action_type": "type_text", "params": {"text": "notepad"}, "description": "输入 notepad"},
            ],
            tags=["notepad", "open"],
        )
        best = host_agent_with_experience._find_reusable_experience("打开记事本")
        assert best is not None
        assert best.task == "打开记事本"
        assert len(best.steps) == 2

    def test_find_reusable_experience_returns_none_when_no_match(self, host_agent_with_experience):
        """没有匹配的经验时返回 None"""
        exp_mgr = host_agent_with_experience.experience
        exp_mgr.record_success(
            task="完全不同的任务",
            steps=[{"action_type": "wait", "params": {}, "description": "等一下"}],
        )
        best = host_agent_with_experience._find_reusable_experience("打开记事本")
        assert best is None

    def test_plan_from_experience(self, host_agent_with_experience):
        """从经验生成计划"""
        exp = Experience(
            exp_id="test_exp_001",
            task="打开记事本",
            steps=[
                StepRecord(step_index=0, action_type="hotkey", params={"keys": ["win", "r"]}, description="打开 Run"),
                StepRecord(step_index=1, action_type="type_text", params={"text": "notepad"}, description="输入 notepad"),
                StepRecord(step_index=2, action_type="hotkey", params={"keys": ["enter"]}, description="回车"),
            ],
            success=True,
            confidence=0.9,
        )
        plan = host_agent_with_experience._plan_from_experience("打开记事本", exp)
        assert plan.goal == "打开记事本"
        assert len(plan.steps) == 3
        assert plan.context["source"] == "experience"
        assert plan.context["experience_confidence"] == 0.9
        assert plan.requires_screenshot is True

    def test_plan_from_experience_skips_invalid_action_type(self, host_agent_with_experience):
        """经验中有无效步骤时跳过"""
        exp = Experience(
            exp_id="test_exp_002",
            task="test",
            steps=[
                StepRecord(step_index=0, action_type="hotkey", params={"keys": ["ctrl", "c"]}, description="copy"),
                StepRecord(step_index=1, action_type="totally_invalid", params={}, description="bad"),
            ],
            success=True,
            confidence=0.85,
        )
        plan = host_agent_with_experience._plan_from_experience("test", exp)
        assert len(plan.steps) == 1  # 无效步骤被跳过

    def test_plan_with_high_confidence_experience(self, host_agent_with_experience):
        """高置信度经验直接返回 plan（不调 MiMo）"""
        exp_mgr = host_agent_with_experience.experience
        exp_mgr.record_success(
            task="打开记事本",
            steps=[
                {"action_type": "hotkey", "params": {"keys": ["win", "r"]}, "description": "Run 对话框"},
                {"action_type": "type_text", "params": {"text": "notepad"}, "description": "输入"},
            ],
            tags=["notepad"],
        )
        # 提升置信度到 0.8+
        exps = exp_mgr.search_similar("打开记事本", success_only=True)
        for e in exps:
            exp_mgr.boost_confidence(e.exp_id, 0.5)

        plan = host_agent_with_experience.plan("打开记事本", "<UIA>")
        assert len(plan.steps) > 0
        assert plan.context.get("source") == "experience"


# ============================================================
# plan() 方法测试
# ============================================================

class TestPlan:
    """测试 plan() 主流程"""

    def test_plan_fallback_without_mimo(self, host_agent):
        """没有 MiMo 时走降级规划"""
        plan = host_agent.plan("打开应用", "<UIA>")
        # 降级规划中 "打开" 会匹配到 hotkey 步骤
        assert plan is not None
        assert isinstance(plan, TaskPlan)

    def test_plan_with_mimo_call(self, host_agent_with_mimo):
        """有 MiMo 时调用 API"""
        mimo_response = json.dumps({
            "analysis": "找到按钮",
            "steps": [{"action": "click", "index": 3, "description": "点击"}],
            "requires_screenshot": True
        })
        host_agent_with_mimo.mimo.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=mimo_response))]
        )
        # Mock retry_call to just call the function directly
        with patch("src.v3.core.host_agent.retry_call", side_effect=lambda fn, **kw: fn()):
            plan = host_agent_with_mimo.plan("点击按钮", "<UIA>")
        assert len(plan.steps) == 1
        assert plan.steps[0].action_type == ActionType.CLICK

    def test_plan_empty_when_api_fails(self, host_agent_with_mimo):
        """MiMo API 失败时返回空 plan"""
        host_agent_with_mimo.mimo.chat.completions.create.side_effect = Exception("API Error")
        with patch("src.v3.core.host_agent.retry_call", side_effect=Exception("API Error")):
            plan = host_agent_with_mimo.plan("test task", "<UIA>")
        # API 失败后 _call_mimo 返回空字符串，_parse_response 解析空字符串返回空 plan
        assert len(plan.steps) == 0


# ============================================================
# _fallback_planning 测试
# ============================================================

class TestFallbackPlanning:
    """测试降级规划"""

    def test_fallback_with_open_keyword(self, host_agent):
        """包含"打开"关键字时生成 Win+R 步骤"""
        response = host_agent._fallback_planning("打开记事本", "<UIA>")
        data = json.loads(response)
        assert "analysis" in data
        assert len(data["steps"]) == 2
        assert data["steps"][0]["action"] == "hotkey"
        assert "win" in data["steps"][0]["keys"]

    def test_fallback_without_open_keyword(self, host_agent):
        """不包含关键字时返回空步骤"""
        response = host_agent._fallback_planning("点击按钮", "<UIA>")
        data = json.loads(response)
        assert len(data["steps"]) == 0
