"""
MCP 插件 - 标准 MCP 协议实现

让 MI Hands 能被所有支持 MCP 的 agent 应用调用
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from ..core.retry_utils import retry_call

from ..core.host_agent import HostAgent
from ..core.app_agent import AppAgent
from ..core.verify import VerifyLayer
from ..core.action_models import TaskPlan, Action, ActionType
from ..core.security import SecurityManager, ActionLogger
from ..core.experience_manager import ExperienceManager
from ..core.learning_loop import LearningLoop
from ..core.smart_verify import SmartVerifyLayer


class MCPPlugin:
    """
    MCP 插件 - 标准 MCP 协议实现

    工具列表：
    - run_task: 执行桌面操作任务（三层架构）
    - snapshot: 获取屏幕状态
    - analyze_screen: AI 分析屏幕
    - click: 点击控件
    - type_text: 输入文字
    - press_key: 按键
    - hotkey: 组合键
    - double_click: 双击控件
    - scroll: 滚动
    - drag: 拖拽
    - wait: 等待
    - list_windows: 列出窗口
    - activate_window: 激活窗口
    """

    name = "mi-hands"
    version = "3.0.0"

    def __init__(self):
        """初始化 MCP 插件"""
        self._engine = None
        self._mimo_client = None
        self._security = SecurityManager()
        self._action_logger = ActionLogger()
        # 三层架构实例（复用，避免冷启动）
        self._host_agent = None
        self._app_agent = None
        self._verify_layer = None
        # 自进化系统
        self._experience_manager = None
        self._smart_verify = None
        self._learning_loop = None

    def _ensure_engine(self):
        """确保 UIA 引擎已初始化"""
        if self._engine is None:
            try:
                import comtypes
                comtypes.CoInitialize()
                from src.uia_engine import UIAEngine
                self._engine = UIAEngine()
            except ImportError as e:
                print(f"UIA 引擎依赖未安装: {e}", file=sys.stderr)
            except Exception as e:
                print(f"UIA 引擎初始化失败: {e}", file=sys.stderr)
        return self._engine

    def _ensure_mimo(self):
        """确保 MiMo 客户端已初始化"""
        if self._mimo_client is None:
            api_key = os.environ.get("MIMO_API_KEY", "")
            if api_key:
                from openai import OpenAI
                self._mimo_client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.xiaomimimo.com/v1"
                )
        return self._mimo_client

    def _ensure_agents(self):
        """确保三层架构实例已初始化（复用，避免冷启动，包含自进化系统）"""
        mimo = self._ensure_mimo()
        engine = self._ensure_engine()

        # 经验管理器（自进化核心）
        if self._experience_manager is None:
            self._experience_manager = ExperienceManager()

        # SmartVerifyLayer（智能验证）
        if self._smart_verify is None:
            self._smart_verify = SmartVerifyLayer(mimo, engine)

        # HostAgent（带经验管理器）
        if self._host_agent is None:
            self._host_agent = HostAgent(mimo, self._experience_manager)

        if self._app_agent is None:
            self._app_agent = AppAgent()

        # VerifyLayer（带 SmartVerify 增强）
        if self._verify_layer is None:
            self._verify_layer = VerifyLayer(mimo, engine, self._smart_verify)

        # LearningLoop（学习循环，串联所有组件）
        if self._learning_loop is None:
            self._learning_loop = LearningLoop(
                verify_layer=self._verify_layer,
                mimo_client=mimo,
                vision_engine=engine,
            )

        return self._host_agent, self._app_agent, self._verify_layer

    def _record_task_experience(self, task: str, plan: TaskPlan,
                                action_results: list, success: bool,
                                error_summary: str = ""):
        """
        将任务结果记录到经验库

        成功的经验：下次可以直接复用步骤
        失败的经验：下次可以避免重复踩坑

        Args:
            task: 任务描述
            plan: 执行计划
            action_results: 操作结果列表
            success: 是否成功
            error_summary: 失败原因（失败时填写）
        """
        if not self._experience_manager:
            return

        # 转换步骤格式
        steps = []
        for ar in action_results:
            steps.append({
                "action_type": ar.action.action_type.value,
                "params": ar.action.params,
                "target_control": ar.action.target_control,
                "description": ar.action.description,
                "success": ar.success,
                "error_msg": ar.message if not ar.success else "",
            })

        # 生成标签（从任务描述提取关键词）
        tags = self._extract_task_tags(task)

        # 记录到经验库
        self._experience_manager.learn_from_task(
            task=task,
            steps=steps,
            success=success,
            error_summary=error_summary,
            tags=tags,
        )

    def _replan_from_feedback(self, task: str, host_agent: HostAgent,
                              feedback) -> TaskPlan:
        """
        根据反馈报告重新规划

        将学习循环的反馈转化为新的执行计划。

        Args:
            task: 任务描述
            host_agent: 决策层实例
            feedback: 反馈报告（FeedbackReport）

        Returns:
            新的执行计划，或 None
        """
        if not self._mimo_client:
            return None

        # 构建包含反馈信息的重新规划 prompt
        suggestions_text = "\n".join(
            f"- {s}" for s in feedback.improvement_suggestions[:5]
        )
        lessons_text = "\n".join(
            f"- {l}" for l in feedback.lessons_learned[:3]
        )

        # 获取当前界面状态
        uia_tree = self._get_uia_tree()
        screenshot = self._get_screenshot_base64()

        prompt = f"""之前的执行失败了，请根据反馈重新规划。

## 用户任务
{task}

## 改进建议
{suggestions_text}

## 经验教训
{lessons_text}

## 当前界面（UIA 控件树）
{uia_tree}

## 要求
1. 避开之前失败的方式
2. 尽量简化步骤
3. 返回 JSON 格式的执行计划

## 返回 JSON 格式
{{
    "analysis": "界面分析 + 失败原因分析",
    "steps": [
        {{
            "action": "操作类型",
            "index": 控件索引,
            "engine": "执行引擎",
            "description": "描述"
        }}
    ],
    "requires_screenshot": true
}}
"""
        try:
            from ..core.retry_utils import retry_call

            messages = [
                {"role": "system", "content": "你是 MI Hands 桌面自动化助手。之前执行失败了，请根据反馈重新规划。返回 JSON 格式。"},
                {"role": "user", "content": prompt},
            ]

            if screenshot:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "当前界面截图："},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}},
                    ],
                })

            def _make_api_call():
                response = self._mimo_client.chat.completions.create(
                    model="mimo-v2.5",
                    messages=messages,
                    max_completion_tokens=4096,
                )
                return response.choices[0].message.content

            content = retry_call(
                _make_api_call, max_retries=2, base_delay=1.0
            )

            return host_agent._parse_response(task, content)

        except Exception as e:
            print(f"重新规划失败: {e}")
            return None

    def _extract_task_tags(self, task: str) -> list:
        """从任务描述中提取标签"""
        tags = []
        tag_keywords = {
            "chrome": ["chrome", "浏览器", "google"],
            "vscode": ["vscode", "代码", "编辑器"],
            "wechat": ["wechat", "微信"],
            "notepad": ["notepad", "记事本"],
            "paint": ["paint", "画图", "绘制", "素描", "draw"],
            "file": ["文件", "file", "保存", "save", "读取", "open"],
            "text": ["文字", "text", "输入", "type"],
        }
        task_lower = task.lower()
        for tag, keywords in tag_keywords.items():
            if any(kw in task_lower for kw in keywords):
                tags.append(tag)
        return tags

    def _get_screenshot_base64(self) -> str:
        """获取截图的 base64 数据"""
        engine = self._ensure_engine()
        if engine:
            try:
                screenshot = engine.take_screenshot()
                if screenshot and hasattr(screenshot, 'base64_data'):
                    return screenshot.base64_data
            except Exception:
                pass
        return ""

    def _get_uia_tree(self) -> str:
        """获取 UIA 树文本"""
        engine = self._ensure_engine()
        if engine:
            try:
                return engine.get_snapshot()
            except Exception:
                pass
        return ""

    def register_tools(self, mcp):
        """
        向 MCP Server 注册所有工具

        参考 UFO 的 ActionReceiver 设计，专注于 MiMo
        """
        plugin = self

        # ============================================================
        # 核心工具：三层架构执行
        # ============================================================

        @mcp.tool()
        def run_task(task: str, max_retries: int = 3) -> str:
            """
            执行桌面操作任务（v3 自进化学习循环）

            流程（自进化学习循环）：
            1. 决策层规划（搜索历史经验 → MiMo 规划）
            2. 执行层执行（UIA + pywinauto + pyautogui）
            3. 验证层检查（SmartVerify 深度诊断）
            4. 失败？分析原因 → 生成反馈 → 再规划
            5. 记录最终成功/失败经验到经验库

            Args:
                task: 任务描述（如 "打开记事本"、"点击确定按钮"）
                max_retries: 最大重试次数

            Returns:
                执行结果（包含学习循环日志）
            """
            import time
            start_time = time.time()

            # 获取当前状态
            uia_tree = plugin._get_uia_tree()
            screenshot = plugin._get_screenshot_base64()

            # 复用三层架构实例（避免冷启动）
            host_agent, app_agent, verify_layer = plugin._ensure_agents()

            # 1. 决策层规划（自动搜索历史经验）
            plan = host_agent.plan(task, uia_tree, screenshot)

            if not plan.steps:
                return f"无法规划任务: {task}"

            results = []
            results.append(f"规划完成: {len(plan.steps)} 个步骤")

            # 如果使用了历史经验，标注来源
            if plan.context.get("source") == "experience":
                exp_id = plan.context.get("experience_id", "")
                conf = plan.context.get("experience_confidence", 0)
                results.append(f"[自进化] 使用历史经验 (置信度: {conf:.0%})")

            # ---- 学习循环：规划 -> 执行 -> 验证 -> 反馈 -> 再规划 ----
            max_learning_cycles = max_retries  # 最大学习循环次数
            all_action_results = []
            final_plan = plan

            for cycle in range(max_learning_cycles):
                if cycle > 0:
                    results.append(f"\n--- 学习循环第 {cycle + 1} 轮 ---")

                # 2. 执行层执行
                cycle_results = []
                for i, action in enumerate(final_plan.steps):
                    result = app_agent.execute(
                        action,
                        plugin._engine._last_tree if plugin._engine else None,
                    )
                    all_action_results.append(result)
                    status = "OK" if result.success else "FAIL"
                    cycle_results.append(
                        f"[{i+1}] {action.description}: {status} {result.message}"
                    )
                results.extend(cycle_results)

                # 3. 验证层检查（使用 SmartVerify 深度诊断）
                if final_plan.requires_screenshot:
                    verification = verify_layer.verify(
                        task, final_plan, max_retries=1,
                        action_results=all_action_results,
                    )
                    if verification.success:
                        results.append("\n验证通过: 任务完成")
                        # 记录成功经验到经验库
                        plugin._record_task_experience(
                            task, final_plan, all_action_results, success=True
                        )
                        break
                    else:
                        results.append(f"\n验证结果: {verification.message}")

                        # 4. 反馈：让学习循环分析失败并调整策略
                        # 生成反馈报告
                        feedback = plugin._learning_loop._generate_feedback(
                            task, verification, all_action_results
                        )

                        # 记录失败经验
                        plugin._record_task_experience(
                            task, final_plan, all_action_results,
                            success=False,
                            error_summary=verification.message,
                        )

                        # 根据反馈重新规划
                        new_plan = plugin._replan_from_feedback(
                            task, host_agent, feedback
                        )
                        if new_plan and new_plan.steps:
                            final_plan = new_plan
                            results.append("根据反馈重新规划")
                        else:
                            results.append("无法生成新计划，结束学习循环")
                            break
                else:
                    # 不需要验证，直接结束
                    plugin._record_task_experience(
                        task, final_plan, all_action_results, success=True
                    )
                    break

            # 记录操作日志
            duration = time.time() - start_time
            plugin._action_logger.log_action(
                action="run_task",
                params={"task": task, "steps": len(all_action_results)},
                result={"success": verification.success if final_plan.requires_screenshot else True},
                duration=duration,
            )

            return "\n".join(results)

        # ============================================================
        # 感知工具
        # ============================================================

        @mcp.tool()
        def snapshot(mode: str = "uia") -> str:
            """
            获取当前屏幕状态

            Args:
                mode: uia(控件树) / screenshot(截图) / both(都要)

            Returns:
                屏幕状态信息
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            if mode == "uia":
                return engine.get_snapshot()
            elif mode == "screenshot":
                ss = engine.take_screenshot()
                if ss and ss.base64_data:
                    return f"[截图: {ss.width}x{ss.height}]\n\n![screenshot](data:image/png;base64,{ss.base64_data})"
                return "❌ 截图失败"
            else:
                tree_text = engine.get_snapshot()
                ss = engine.take_screenshot()
                if ss and ss.base64_data:
                    return f"{tree_text}\n\n![screenshot](data:image/png;base64,{ss.base64_data})"
                return tree_text

        @mcp.tool()
        def analyze_screen(task: str = "") -> str:
            """
            用 MiMo 视觉模型分析屏幕（带重试机制）

            Args:
                task: 分析任务（可选）

            Returns:
                分析结果
            """
            mimo = plugin._ensure_mimo()
            if not mimo:
                return "❌ MIMO_API_KEY 未设置"

            uia_tree = plugin._get_uia_tree()
            screenshot = plugin._get_screenshot_base64()

            if not screenshot:
                return "❌ 截图失败"

            def _make_api_call():
                prompt = f"""分析当前屏幕状态。

## 任务
{task if task else "分析界面布局和可用操作"}

## UIA 控件树
{uia_tree}

## 要求
1. 描述当前界面
2. 列出可用操作
3. 给出操作建议

返回 JSON 格式：
{{
    "analysis": "界面分析",
    "available_actions": ["操作1", "操作2"],
    "suggestions": ["建议1", "建议2"]
}}
"""

                messages = [
                    {"role": "system", "content": "你是 MI Hands 视觉分析助手。返回 JSON 格式。"},
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": "当前界面截图："},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}}
                    ]}
                ]

                # 调用 MiMo API
                response = mimo.chat.completions.create(
                    model="mimo-v2.5",
                    messages=messages,
                    max_completion_tokens=4096,
                )

                return response.choices[0].message.content

            try:
                # 带重试的 API 调用
                return retry_call(
                    _make_api_call,
                    max_retries=3,
                    base_delay=1.0,
                    max_delay=10.0,
                )
            except Exception as e:
                return f"❌ 分析失败（已重试 3 次）: {e}"

        # ============================================================
        # 操作工具
        # ============================================================

        @mcp.tool()
        def click(x: int = 0, y: int = 0, index: int = -1, button: str = "left") -> str:
            """
            点击控件

            Args:
                x: X 坐标（坐标点击时使用）
                y: Y 坐标（坐标点击时使用）
                index: 控件索引（UIA 树中的编号）
                button: 鼠标按钮（left/right）

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            if index >= 0:
                return engine.click_node(index)

            import pyautogui
            if button == "right":
                pyautogui.rightClick(x, y)
            else:
                pyautogui.click(x, y)
            return f"✅ 已点击 ({x}, {y})"

        @mcp.tool()
        def double_click(x: int = 0, y: int = 0, index: int = -1) -> str:
            """
            双击控件

            Args:
                x: X 坐标
                y: Y 坐标
                index: 控件索引

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            if index >= 0 and engine._last_tree:
                if index < len(engine._last_tree.nodes):
                    node = engine._last_tree.nodes[index]
                    if node.rect:
                        x = (node.rect[0] + node.rect[2]) // 2
                        y = (node.rect[1] + node.rect[3]) // 2

                        # 记住当前前台窗口
                        try:
                            import win32gui
                            original_window = win32gui.GetForegroundWindow()
                        except:
                            original_window = None

                        import pyautogui
                        pyautogui.doubleClick(x, y)

                        # 重新激活原窗口
                        if original_window:
                            import time
                            time.sleep(0.1)
                            try:
                                import win32gui
                                win32gui.SetForegroundWindow(original_window)
                            except:
                                pass

                        return f"✅ 双击 [{index}] {node.name} ({x}, {y})"

            import pyautogui
            pyautogui.doubleClick(x, y)
            return f"✅ 双击 ({x}, {y})"

        @mcp.tool()
        def type_text(text: str, index: int = -1) -> str:
            """
            输入文字

            Args:
                text: 要输入的文字
                index: 目标控件索引（可选）

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            if index >= 0:
                return engine.type_text(text, index)

            # 降级：剪贴板粘贴
            import pyautogui
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return f"✅ 已输入: {text[:50]}{'...' if len(text) > 50 else ''}"

        @mcp.tool()
        def press_key(key: str = "enter") -> str:
            """
            按键

            Args:
                key: 按键名称（enter, tab, escape, backspace, delete, up, down, left, right, space）

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            return engine.press_key(key)

        @mcp.tool()
        def hotkey(keys: list[str] = None) -> str:
            """
            组合键

            Args:
                keys: 按键列表（如 ["ctrl", "s"]）

            Returns:
                执行结果
            """
            if not keys:
                return "❌ 请指定按键"

            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            return engine.hotkey(keys)

        @mcp.tool()
        def scroll(x: int = 960, y: int = 540, delta: int = -3) -> str:
            """
            滚动

            Args:
                x: X 坐标
                y: Y 坐标
                delta: 滚动量（正数向上，负数向下）

            Returns:
                执行结果
            """
            import pyautogui
            pyautogui.scroll(delta, x, y)
            direction = "向上" if delta > 0 else "向下"
            return f"✅ 滚动 {direction} {abs(delta)} 格"

        @mcp.tool()
        def drag(x1: int = 0, y1: int = 0, x2: int = 100, y2: int = 100) -> str:
            """
            拖拽

            Args:
                x1: 起点 X
                y1: 起点 Y
                x2: 终点 X
                y2: 终点 Y

            Returns:
                执行结果
            """
            import pyautogui
            pyautogui.moveTo(x1, y1)
            pyautogui.mouseDown()
            pyautogui.moveTo(x2, y2, duration=0.5)
            pyautogui.mouseUp()
            return f"✅ 拖拽: ({x1},{y1}) -> ({x2},{y2})"

        @mcp.tool()
        def wait(seconds: float = 1.0) -> str:
            """
            等待指定秒数

            Args:
                seconds: 等待秒数

            Returns:
                执行结果
            """
            import time
            time.sleep(seconds)
            return f"✅ 已等待 {seconds} 秒"

        # ============================================================
        # 手绘工具
        # ============================================================

        @mcp.tool()
        def draw_path(points: list[list[int]], speed: float = 0.01) -> str:
            """
            像人一样手绘路径 — 按住鼠标连续移动

            Args:
                points: 路径点列表，如 [[100,200], [150,250], [200,300]]
                speed: 移动速度（秒/点），越小越快

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            try:
                import pyautogui
                import time

                if not points or len(points) < 2:
                    return "❌ 至少需要 2 个点"

                # 移动到起点
                start = points[0]
                pyautogui.moveTo(start[0], start[1])

                # 按住鼠标
                pyautogui.mouseDown()

                # 连续移动到每个点
                for point in points[1:]:
                    pyautogui.moveTo(point[0], point[1])
                    time.sleep(speed)

                # 释放鼠标
                pyautogui.mouseUp()

                return f"✅ 绘制路径完成: {len(points)} 个点"
            except Exception as e:
                return f"❌ 绘制路径失败: {e}"

        @mcp.tool()
        def draw_curve(
            start: list[int],
            end: list[int],
            control: list[int],
            segments: int = 20,
            speed: float = 0.01
        ) -> str:
            """
            绘制贝塞尔曲线 — 用于画弧线、圆角等

            Args:
                start: 起点 [x, y]
                end: 终点 [x, y]
                control: 控制点 [x, y]
                segments: 曲线分段数（越多越平滑）
                speed: 移动速度

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            try:
                import pyautogui
                import time

                # 计算贝塞尔曲线点
                points = []
                for i in range(segments + 1):
                    t = i / segments
                    x = (1-t)**2 * start[0] + 2*(1-t)*t * control[0] + t**2 * end[0]
                    y = (1-t)**2 * start[1] + 2*(1-t)*t * control[1] + t**2 * end[1]
                    points.append((int(x), int(y)))

                # 绘制
                pyautogui.moveTo(points[0][0], points[0][1])
                pyautogui.mouseDown()
                for point in points[1:]:
                    pyautogui.moveTo(point[0], point[1])
                    time.sleep(speed)
                pyautogui.mouseUp()

                return f"✅ 绘制曲线完成: {segments} 段"
            except Exception as e:
                return f"❌ 绘制曲线失败: {e}"

        @mcp.tool()
        def draw_circle(
            center: list[int],
            radius: int,
            segments: int = 36,
            speed: float = 0.01
        ) -> str:
            """
            绘制圆形

            Args:
                center: 圆心 [x, y]
                radius: 半径
                segments: 分段数（越多越圆）
                speed: 移动速度

            Returns:
                执行结果
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            try:
                import pyautogui
                import time
                import math

                # 计算圆形点
                points = []
                for i in range(segments + 1):
                    angle = 2 * math.pi * i / segments
                    x = center[0] + radius * math.cos(angle)
                    y = center[1] + radius * math.sin(angle)
                    points.append((int(x), int(y)))

                # 绘制
                pyautogui.moveTo(points[0][0], points[0][1])
                pyautogui.mouseDown()
                for point in points[1:]:
                    pyautogui.moveTo(point[0], point[1])
                    time.sleep(speed)
                pyautogui.mouseUp()

                return f"✅ 绘制圆形完成: 半径 {radius}, {segments} 段"
            except Exception as e:
                return f"❌ 绘制圆形失败: {e}"

        # ============================================================
        # 窗口管理工具
        # ============================================================

        @mcp.tool()
        def list_windows() -> str:
            """
            列出所有可操作的窗口

            Returns:
                窗口列表
            """
            engine = plugin._ensure_engine()
            if not engine:
                return "❌ UIA 引擎未初始化"

            try:
                import uiautomation as auto
                windows = auto.GetRootControl().GetChildren()
                result = []
                for w in windows:
                    try:
                        name = w.Name
                        handle = w.NativeWindowHandle
                        if name and handle:
                            result.append(f"[{handle}] {name}")
                    except:
                        continue
                return "\n".join(result) if result else "❌ 没有找到窗口"
            except Exception as e:
                return f"❌ 获取窗口列表失败: {e}"

        @mcp.tool()
        def activate_window(window_handle: int = 0) -> str:
            """
            激活指定窗口

            Args:
                window_handle: 窗口句柄

            Returns:
                执行结果
            """
            if not window_handle:
                return "❌ 请指定窗口句柄"

            try:
                import win32gui
                win32gui.SetForegroundWindow(window_handle)
                return f"✅ 已激活窗口: {window_handle}"
            except Exception as e:
                return f"❌ 激活窗口失败: {e}"

        # ============================================================
        # Skill 管理工具
        # ============================================================

        @mcp.tool()
        def find_skill(query: str) -> str:
            """
            搜索 skill（本地 + GitHub）

            根据关键词搜索可用的 skill，包括本地已安装的和 GitHub 上的。

            Args:
                query: 搜索关键词（如 "sketch", "paint", "krita"）

            Returns:
                搜索结果
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                results = manager.search(query)

                output = []

                # 本地 skill
                local = results.get("local", [])
                if local:
                    output.append("📚 本地已安装的 skill:")
                    for skill in local:
                        output.append(f"  - {skill.get('name')}: {skill.get('description', '')[:50]}")
                else:
                    output.append("📚 本地暂无匹配的 skill")

                # GitHub skill
                github = results.get("github", [])
                if github:
                    output.append("\n🌐 GitHub 上的 skill:")
                    for repo in github:
                        stars = repo.get("stars", 0)
                        output.append(f"  - {repo.get('name')}: {repo.get('description', '')[:50]} ⭐{stars}")
                        output.append(f"    URL: {repo.get('url', '')}")
                else:
                    output.append("\n🌐 GitHub 暂无匹配的 skill")

                return "\n".join(output)

            except Exception as e:
                return f"❌ 搜索 skill 失败: {e}"

        @mcp.tool()
        def install_skill(skill_url: str) -> str:
            """
            安装 skill 到本地

            从 GitHub 仓库下载并安装 skill。

            Args:
                skill_url: GitHub 仓库 URL（如 "https://github.com/user/repo"）

            Returns:
                安装结果
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                # 下载 skill
                skill_data = manager.download_skill(skill_url)
                if not skill_data:
                    return f"❌ 下载 skill 失败: {skill_url}"

                # 安装
                success = manager.install_skill(skill_data)
                if success:
                    return f"✅ Skill '{skill_data.get('name')}' 安装成功！"
                else:
                    return f"❌ 安装 skill 失败"

            except Exception as e:
                return f"❌ 安装 skill 失败: {e}"

        @mcp.tool()
        def list_skills() -> str:
            """
            列出已安装的 skill

            Returns:
                已安装的 skill 列表
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                skills = manager.list_installed_skills()

                if not skills:
                    return "📚 暂无已安装的 skill\n\n使用 find_skill() 搜索可用的 skill"

                output = [f"📚 已安装 {len(skills)} 个 skill:\n"]

                for skill in skills:
                    name = skill.get("name", "")
                    desc = skill.get("description", "")[:50]
                    tags = skill.get("tags", [])
                    output.append(f"• {name}")
                    output.append(f"  {desc}")
                    if tags:
                        output.append(f"  标签: {', '.join(tags)}")
                    output.append("")

                return "\n".join(output)

            except Exception as e:
                return f"❌ 获取 skill 列表失败: {e}"

        @mcp.tool()
        def uninstall_skill(skill_name: str) -> str:
            """
            卸载 skill

            Args:
                skill_name: skill 名称

            Returns:
                卸载结果
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                success = manager.uninstall_skill(skill_name)
                if success:
                    return f"✅ Skill '{skill_name}' 已卸载"
                else:
                    return f"❌ 卸载 skill 失败"

            except Exception as e:
                return f"❌ 卸载 skill 失败: {e}"

        @mcp.tool()
        def share_skill(skill_name: str) -> str:
            """
            分享 skill 到 GitHub

            准备 skill 的分享数据，生成仓库名和文件内容。

            Args:
                skill_name: skill 名称

            Returns:
                分享指南
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                share_data = manager.create_share_repo_data(skill_name)
                if not share_data:
                    return f"❌ 准备分享数据失败"

                repo_name = share_data.get("repo_name", "")
                description = share_data.get("description", "")
                topics = share_data.get("topics", [])

                output = [
                    f"📤 准备分享 skill: {skill_name}\n",
                    f"建议的仓库名: {repo_name}",
                    f"描述: {description}",
                    f"标签: {', '.join(topics)}\n",
                    "📁 需要上传的文件:",
                ]

                for filename in share_data.get("files", {}).keys():
                    output.append(f"  - {filename}")

                output.append("\n📋 分享步骤:")
                output.append("1. 在 GitHub 创建仓库: " + repo_name)
                output.append("2. 上传 skill.json 和 README.md")
                output.append("3. 添加标签: " + ", ".join(topics))
                output.append("4. 其他人可以通过 find_skill() 搜索到你的 skill")

                return "\n".join(output)

            except Exception as e:
                return f"❌ 准备分享数据失败: {e}"

        @mcp.tool()
        def create_skill(
            name: str,
            description: str,
            prompt: str,
            tags: list[str] = None
        ) -> str:
            """
            创建新的 skill

            创建一个本地 skill，可以稍后分享到 GitHub。

            Args:
                name: skill 名称（英文，用连字符分隔）
                description: skill 描述
                prompt: skill 的 prompt（指导 AI 如何执行任务）
                tags: 标签列表

            Returns:
                创建结果
            """
            try:
                from ..core.skill_manager import SkillManager
                manager = SkillManager()

                skill_data = {
                    "name": name,
                    "version": "1.0.0",
                    "description": description,
                    "prompt": prompt,
                    "tags": tags or [],
                    "author": "",
                    "examples": [],
                }

                success = manager.install_skill(skill_data)
                if success:
                    return f"✅ Skill '{name}' 创建成功！\n\n使用 share_skill('{name}') 可以分享到 GitHub"
                else:
                    return f"❌ 创建 skill 失败"

            except Exception as e:
                return f"❌ 创建 skill 失败: {e}"

        # ============================================================
        # 脚本执行工具
        # ============================================================

        @mcp.tool()
        def execute_script(code: str, language: str = "python") -> str:
            """
            执行脚本代码（带安全检查）

            Args:
                code: 代码内容
                language: 语言（python/shell/batch）

            Returns:
                执行结果
            """
            import time
            start_time = time.time()

            try:
                from ..core.script_executor import ScriptExecutor
                executor = ScriptExecutor()

                if language == "python":
                    result = executor.execute_python(code)
                elif language == "shell":
                    result = executor.execute_shell(code)
                elif language == "batch":
                    result = executor.execute_batch(code)
                else:
                    return f"❌ 不支持的语言: {language}"

                # 记录操作日志
                duration = time.time() - start_time
                plugin._action_logger.log_action(
                    action=f"execute_script:{language}",
                    params={"code_length": len(code)},
                    result=result,
                    duration=duration,
                )

                output = []
                if result["success"]:
                    output.append("✅ 脚本执行成功")
                else:
                    output.append("❌ 脚本执行失败")

                if result["output"]:
                    output.append(f"\n输出:\n{result['output'][:500]}")
                if result["error"]:
                    output.append(f"\n错误:\n{result['error'][:500]}")

                return "\n".join(output)

            except Exception as e:
                return f"❌ Script execution failed: {e}"

        # ============================================================
        # 文件操作工具
        # ============================================================

        @mcp.tool()
        def read_file(path: str) -> str:
            """
            读取文件内容

            Args:
                path: 文件路径

            Returns:
                文件内容
            """
            try:
                from ..core.file_ops import FileOperations
                ops = FileOperations(base_path=str(Path.home()))

                result = ops.read_file(path)
                if result["success"]:
                    return f"OK: File content\n\n{result['content'][:2000]}"
                else:
                    return f"❌ {result['error']}"

            except Exception as e:
                return f"❌ Read file failed: {e}"

        @mcp.tool()
        def write_file(path: str, content: str) -> str:
            """
            写入文件（带安全检查）

            Args:
                path: 文件路径
                content: 文件内容

            Returns:
                写入结果
            """
            import time
            start_time = time.time()

            try:
                from ..core.file_ops import FileOperations
                ops = FileOperations(base_path=str(Path.home()))

                result = ops.write_file(path, content)

                # 记录操作日志
                duration = time.time() - start_time
                plugin._action_logger.log_action(
                    action="write_file",
                    params={"path": path, "content_length": len(content)},
                    result=result,
                    duration=duration,
                )

                if result["success"]:
                    return f"✅ 文件写入成功: {path}"
                else:
                    return f"❌ {result['error']}"

            except Exception as e:
                return f"❌ 写入文件失败: {e}"

        @mcp.tool()
        def list_files(path: str = ".", pattern: str = None) -> str:
            """
            列出目录内容

            Args:
                path: 目录路径
                pattern: 过滤模式（如 "*.py"）

            Returns:
                文件列表
            """
            try:
                from ..core.file_ops import FileOperations
                ops = FileOperations(base_path=str(Path.home()))

                result = ops.list_dir(path, pattern)
                if result["success"]:
                    items = result["items"]
                    output = [f"Found {len(items)} items:\n"]
                    for item in items[:50]:  # 限制显示数量
                        prefix = "[DIR] " if item["is_dir"] else "      "
                        output.append(f"{prefix}{item['name']}")
                    return "\n".join(output)
                else:
                    return f"❌ {result['error']}"

            except Exception as e:
                return f"❌ List files failed: {e}"

        @mcp.tool()
        def search_files(pattern: str, path: str = ".") -> str:
            """
            搜索文件

            Args:
                pattern: 搜索模式（如 "*.json", "**/*.py"）
                path: 搜索路径

            Returns:
                搜索结果
            """
            try:
                from ..core.file_ops import FileOperations
                ops = FileOperations(base_path=str(Path.home()))

                result = ops.search_files(pattern, path)
                if result["success"]:
                    files = result["files"]
                    output = [f"Found {len(files)} files:\n"]
                    for f in files[:50]:
                        output.append(f"  {f}")
                    return "\n".join(output)
                else:
                    return f"❌ {result['error']}"

            except Exception as e:
                return f"❌ Search files failed: {e}"

        # ============================================================
        # 性能监控工具
        # ============================================================

        @mcp.tool()
        def get_metrics() -> str:
            """
            获取性能指标

            Returns:
                性能报告
            """
            try:
                from ..core.metrics import MetricsCollector
                collector = MetricsCollector()

                return collector.export_report()

            except Exception as e:
                return f"❌ Get metrics failed: {e}"

        @mcp.tool()
        def get_action_history(limit: int = 10) -> str:
            """
            获取操作历史

            Args:
                limit: 返回数量

            Returns:
                操作历史
            """
            try:
                from ..core.security import SecurityManager
                security = SecurityManager()

                history = security.get_history(limit)
                if not history:
                    return "No action history available"

                output = [f"Recent {len(history)} actions:\n"]
                for entry in history:
                    timestamp = entry.get("timestamp", "")
                    action = entry.get("action", "")
                    success = entry.get("success", False)
                    duration = entry.get("duration", 0)
                    status = "OK" if success else "FAIL"
                    output.append(f"[{timestamp}] {action}: {status} ({duration:.2f}s)")

                return "\n".join(output)

            except Exception as e:
                return f"❌ Get action history failed: {e}"

        @mcp.tool()
        def rollback(steps: int = 1) -> str:
            """
            回滚操作

            Args:
                steps: 回滚步数

            Returns:
                回滚结果
            """
            try:
                from ..core.security import SecurityManager
                security = SecurityManager()

                result = security.rollback.rollback(steps)
                if result:
                    output = [f"Rolled back {len(result)} steps:\n"]
                    for entry in result:
                        output.append(f"  - {entry.get('action', 'unknown')} ({entry.get('timestamp', '')})")
                    return "\n".join(output)
                else:
                    return "No rollback data available"

            except Exception as e:
                return f"❌ Rollback failed: {e}"

        # ============================================================
        # 记忆系统工具
        # ============================================================

        @mcp.tool()
        def get_memory_stats() -> str:
            """
            获取记忆系统统计

            Returns:
                记忆统计信息
            """
            try:
                from ..core.memory import MemoryManager
                memory = MemoryManager()

                stats = memory.get_stats()
                output = [
                    "Memory Stats:",
                    f"  Short-term: {stats['short_term_count']} entries",
                    f"  Long-term tasks: {stats['long_term_tasks']}",
                    f"  Long-term errors: {stats['long_term_errors']}",
                    f"  Long-term successes: {stats['long_term_successes']}",
                    f"  Working memory: {stats['working_memory_keys']}",
                ]

                return "\n".join(output)

            except Exception as e:
                return f"❌ Get memory stats failed: {e}"

        @mcp.tool()
        def get_learning_stats() -> str:
            """
            获取学习系统统计

            Returns:
                学习统计信息
            """
            try:
                from ..core.reflection import ReflectionManager
                reflection = ReflectionManager()

                stats = reflection.get_stats()
                output = [
                    "Learning Stats:",
                    f"  Error patterns: {stats['error_patterns_count']}",
                    f"  Success patterns: {stats['success_patterns_count']}",
                    f"  Improvements: {stats['improvements_count']}",
                    f"  Total errors: {stats['total_errors']}",
                    f"  Total successes: {stats['total_successes']}",
                ]

                return "\n".join(output)

            except Exception as e:
                return f"❌ Get learning stats failed: {e}"


def create_mcp_server():
    """
    创建 MCP 服务器

    用于独立运行 MCP 模式
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("请安装 MCP: pip install mcp", file=sys.stderr)
        sys.exit(1)

    mcp = FastMCP("MI Hands")
    plugin = MCPPlugin()
    plugin.register_tools(mcp)
    return mcp


def main():
    """MCP 模式入口"""
    mcp = create_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()
