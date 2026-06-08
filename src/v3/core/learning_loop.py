"""
LearningLoop - 学习循环模块

负责闭环反馈：规划 → 执行 → 验证 → 反馈 → 再规划

核心流程：
1. 验证层判断任务是否真正完成
2. 如果未完成，分析当前界面状态
3. 生成改进建议返回给决策层
4. 决策层根据反馈调整策略

参考 UFO 的 RetryCoordinator + Reflection 设计，
结合 MiMo 的视觉理解能力实现闭环学习。
"""

import json
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

from .action_models import Action, TaskPlan, TaskResult, ActionType
from .verify import VerifyLayer
from .reflection import ReflectionManager
from .continuous_awareness import ContinuousAwareness


@dataclass
class LoopState:
    """学习循环的当前状态"""
    task: str                              # 用户任务
    current_plan: Optional[TaskPlan]       # 当前执行计划
    attempt: int = 0                       # 当前尝试次数
    max_attempts: int = 5                  # 最大尝试次数
    history: List[Dict] = field(default_factory=list)  # 每轮历史记录
    success: bool = False                  # 是否已成功
    final_message: str = ""                # 最终消息
    start_time: float = 0.0               # 开始时间
    feedback_chain: List[str] = field(default_factory=list)  # 反馈链（累积改进建议）


@dataclass
class VerificationResult:
    """验证结果（增强版，包含诊断信息）"""
    completed: bool                        # 任务是否完成
    reason: str = ""                       # 判断原因
    suggestion: str = ""                   # 改进建议
    diagnosis: Dict = field(default_factory=dict)  # 界面诊断信息
    confidence: float = 0.0               # 判断置信度 (0-1)


@dataclass
class FeedbackReport:
    """反馈报告（给决策层的改进输入）"""
    cycle_number: int                      # 第几轮循环
    verification: VerificationResult       # 验证结果
    failed_actions: List[Dict]             # 失败的动作
    interface_changes: Dict                # 界面变化分析
    improvement_suggestions: List[str]     # 改进建议列表
    strategy_adjustments: Dict             # 策略调整建议
    lessons_learned: List[str]             # 本轮学到的经验


class LearningLoop:
    """
    学习循环 - 闭环反馈系统

    把三层架构串成一个闭环：
    规划(HostAgent) → 执行(AppAgent) → 验证(VerifyLayer) → 反馈(LearningLoop) → 再规划

    核心思想：
    - 不是简单重试，而是"分析失败原因 → 调整策略 → 再执行"
    - 每次失败都积累经验，下一次更好
    - 自动降级：AI 不行就用规则，规则不行就用历史
    """

    def __init__(
        self,
        verify_layer: VerifyLayer = None,
        reflection: ReflectionManager = None,
        mimo_client=None,
        vision_engine=None,
    ):
        """
        初始化学习循环

        Args:
            verify_layer: 验证层实例
            reflection: 反思学习系统
            mimo_client: MiMo API 客户端（用于 AI 分析）
            vision_engine: 视觉引擎（用于截图和 UIA 树）
        """
        self.verify = verify_layer or VerifyLayer(mimo_client, vision_engine)
        self.reflection = reflection or ReflectionManager()
        self.mimo = mimo_client
        self.vision = vision_engine
        self.awareness = ContinuousAwareness(vision_engine)

        # 循环历史（所有任务的记录）
        self.loop_history: List[Dict] = []

    # ============================================================
    # 主循环入口
    # ============================================================

    def run(
        self,
        task: str,
        plan: TaskPlan,
        executor=None,
        max_attempts: int = 5,
        on_feedback=None,
    ) -> TaskResult:
        """
        运行完整的学 习循环

        流程：
        1. 执行计划
        2. 验证结果
        3. 如果失败，分析原因，生成反馈
        4. 调用 on_feedback 让决策层调整策略
        5. 用新计划重新执行
        6. 直到成功或达到最大尝试次数

        Args:
            task: 用户任务
            plan: 初始执行计划
            executor: 执行器（AppAgent 实例），负责实际执行动作
            max_attempts: 最大尝试次数
            on_feedback: 回调函数，签名 (task, feedback) -> TaskPlan
                         接收反馈报告，返回新的执行计划

        Returns:
            TaskResult: 最终任务结果
        """
        state = LoopState(
            task=task,
            current_plan=plan,
            max_attempts=max_attempts,
            start_time=time.time(),
        )

        for attempt in range(max_attempts):
            state.attempt = attempt + 1

            # ---- 阶段 1: 执行 ----
            exec_result = self._execute_plan(state.current_plan, executor)

            # ---- 阶段 2: 验证 ----
            verification = self._verify_task(task)

            # ---- 阶段 3: 记录本轮历史 ----
            cycle_record = {
                "attempt": state.attempt,
                "plan_summary": self._summarize_plan(state.current_plan),
                "exec_result": {
                    "success": exec_result.success,
                    "message": exec_result.message,
                    "steps_completed": exec_result.steps_completed,
                },
                "verification": {
                    "completed": verification.completed,
                    "reason": verification.reason,
                    "suggestion": verification.suggestion,
                },
                "timestamp": datetime.now().isoformat(),
            }
            state.history.append(cycle_record)

            # ---- 阶段 4: 判断是否完成 ----
            if verification.completed:
                state.success = True
                state.final_message = f"任务在第 {state.attempt} 轮完成"
                self._on_task_complete(state, exec_result)
                return self._build_final_result(state, exec_result)

            # ---- 阶段 5: 分析失败，生成反馈 ----
            failed_actions = self._collect_failed_actions(exec_result)
            feedback = self._generate_feedback(state, verification, failed_actions)

            # 记录到反思系统
            self._record_failure(task, verification, failed_actions)

            # ---- 阶段 6: 调整策略 ----
            if on_feedback:
                # 让决策层根据反馈调整策略
                new_plan = on_feedback(task, feedback)
                if new_plan:
                    state.current_plan = new_plan
                    state.feedback_chain.append(verification.suggestion)
                else:
                    # 决策层无法生成新计划，尝试自动降级
                    new_plan = self._fallback_replan(task, state, verification)
                    if new_plan:
                        state.current_plan = new_plan
                    else:
                        # 彻底无法继续
                        state.final_message = f"第 {state.attempt} 轮失败，无法生成新计划"
                        break
            else:
                # 没有回调，用自动降级策略
                new_plan = self._fallback_replan(task, state, verification)
                if new_plan:
                    state.current_plan = new_plan
                else:
                    state.final_message = f"第 {state.attempt} 轮失败，无法生成新计划"
                    break

        # 循环结束，任务未完成
        elapsed = time.time() - state.start_time
        state.final_message = (
            f"任务未完成: {state.final_message or '超过最大尝试次数'} "
            f"(共 {state.attempt} 轮, 耗时 {elapsed:.1f}s)"
        )

        return TaskResult(
            goal=task,
            success=False,
            message=state.final_message,
            steps_completed=0,
            steps_total=len(state.current_plan.steps) if state.current_plan else 0,
            retries=state.attempt,
        )

    # ============================================================
    # 执行阶段
    # ============================================================

    def _execute_plan(self, plan: TaskPlan, executor=None) -> TaskResult:
        """
        执行一个计划（串行执行所有步骤）

        Args:
            plan: 要执行的计划
            executor: 执行器（AppAgent）

        Returns:
            TaskResult: 执行结果
        """
        if not plan or not plan.steps:
            return TaskResult(
                goal=plan.goal if plan else "",
                success=False,
                message="空计划，无步骤可执行",
            )

        result = TaskResult(
            goal=plan.goal,
            success=False,
            steps_total=len(plan.steps),
        )

        for i, action in enumerate(plan.steps):
            try:
                if executor:
                    # 用 AppAgent 执行
                    action_result = executor.execute(action)
                else:
                    # 没有执行器，标记为模拟成功
                    action_result = _mock_execute(action)

                result.action_results.append(action_result)
                result.steps_completed = i + 1

                if not action_result.success:
                    result.message = f"步骤 {i+1} 失败: {action_result.message}"
                    # 不立即中断，继续执行后续步骤（收集更多信息）
                    continue

            except Exception as e:
                result.action_results.append(ActionResult(
                    action=action,
                    success=False,
                    message=f"执行异常: {e}",
                ))
                result.message = f"步骤 {i+1} 异常: {e}"
                continue

        # 判断整体是否成功
        if result.steps_completed == len(plan.steps):
            all_success = all(r.success for r in result.action_results)
            result.success = all_success
            if all_success:
                result.message = "所有步骤执行成功"
            else:
                failed_count = sum(1 for r in result.action_results if not r.success)
                result.message = f"{failed_count}/{len(plan.steps)} 个步骤失败"

        return result

    # ============================================================
    # 验证阶段
    # ============================================================

    def _verify_task(self, task: str) -> VerificationResult:
        """
        验证任务是否完成（增强版，带界面诊断）

        Args:
            task: 用户任务

        Returns:
            VerificationResult: 验证结果
        """
        # 获取当前界面状态
        screenshot = self._take_screenshot()
        uia_tree = self._get_uia_tree()

        # AI 判断
        if self.mimo:
            raw_judgment = self._judge_with_mimo(task, screenshot, uia_tree)
        else:
            raw_judgment = self._judge_fallback(task, uia_tree)

        # 分析界面状态
        diagnosis = self._diagnose_interface(uia_tree, screenshot)

        # 判断置信度
        confidence = self._calculate_confidence(raw_judgment, diagnosis)

        return VerificationResult(
            completed=raw_judgment.get("completed", False),
            reason=raw_judgment.get("reason", ""),
            suggestion=raw_judgment.get("suggestion", ""),
            diagnosis=diagnosis,
            confidence=confidence,
        )

    def _diagnose_interface(self, uia_tree: str, screenshot: str) -> Dict:
        """
        诊断当前界面状态

        分析 UIA 树，提取有用信息：
        - 当前窗口标题
        - 可见的控件
        - 是否有错误弹窗
        - 界面是否卡死

        Args:
            uia_tree: UIA 树文本
            screenshot: 截图 base64

        Returns:
            诊断信息字典
        """
        diagnosis = {
            "has_uia_tree": bool(uia_tree),
            "has_screenshot": bool(screenshot),
            "error_dialog_detected": False,
            "controls_count": 0,
            "window_changed": False,
            "stuck_detected": False,
        }

        if not uia_tree:
            return diagnosis

        # 统计控件数量
        diagnosis["controls_count"] = uia_tree.count("\n")

        # 检测错误弹窗
        error_keywords = ["error", "错误", "失败", "exception", "timeout", "无法"]
        uia_lower = uia_tree.lower()
        for keyword in error_keywords:
            if keyword in uia_lower:
                diagnosis["error_dialog_detected"] = True
                diagnosis["error_keyword"] = keyword
                break

        # 检测界面是否变化（和上次快照比较）
        change_result = self.awareness.detect_changes()
        diagnosis["window_changed"] = change_result.get("changed", False)

        # 检测界面是否卡死（连续两次快照完全一样）
        if not change_result.get("changed", True):
            diagnosis["stuck_detected"] = True

        return diagnosis

    def _calculate_confidence(self, judgment: Dict, diagnosis: Dict) -> float:
        """
        计算验证判断的置信度

        综合多个因素：
        - AI 判断的明确程度
        - 界面诊断结果
        - 是否有错误弹窗

        Args:
            judgment: AI 原始判断
            diagnosis: 界面诊断

        Returns:
            置信度 (0-1)
        """
        confidence = 0.5  # 基础置信度

        # 如果有截图，置信度更高
        if diagnosis.get("has_screenshot"):
            confidence += 0.2

        # 如果有 UIA 树，置信度更高
        if diagnosis.get("has_uia_tree"):
            confidence += 0.1

        # 如果检测到错误弹窗，未完成的判断更可信
        if diagnosis.get("error_dialog_detected"):
            if not judgment.get("completed", True):
                confidence += 0.15

        # 如果界面卡死，可能判断不准
        if diagnosis.get("stuck_detected"):
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    # ============================================================
    # 反馈分析阶段
    # ============================================================

    def _generate_feedback(
        self,
        state: LoopState,
        verification: VerificationResult,
        failed_actions: List[Dict],
    ) -> FeedbackReport:
        """
        生成反馈报告

        综合分析失败原因，给出改进建议。

        Args:
            state: 循环状态
            verification: 验证结果
            failed_actions: 失败的动作列表

        Returns:
            FeedbackReport: 反馈报告
        """
        # 收集改进建议
        suggestions = []

        # 1. 来自验证层的建议
        if verification.suggestion:
            suggestions.append(f"验证建议: {verification.suggestion}")

        # 2. 来自失败动作的分析
        for failed in failed_actions:
            action_desc = failed.get("description", "未知动作")
            error_msg = failed.get("error", "未知错误")
            suggestions.append(f"动作失败 [{action_desc}]: {error_msg}")

        # 3. 来自界面诊断
        if verification.diagnosis.get("error_dialog_detected"):
            keyword = verification.diagnosis.get("error_keyword", "")
            suggestions.append(f"检测到错误弹窗 (关键词: {keyword})，需要先处理弹窗")

        if verification.diagnosis.get("stuck_detected"):
            suggestions.append("界面疑似卡死，建议等待或切换策略")

        # 4. 来自历史经验
        history_suggestions = self.reflection.get_improved_prompt(state.task)
        if history_suggestions:
            suggestions.append(f"历史经验: {history_suggestions}")

        # 5. 来自累积反馈链
        if state.feedback_chain:
            suggestions.append(
                f"之前 {len(state.feedback_chain)} 轮的累积反馈: "
                + "; ".join(state.feedback_chain[-3:])  # 最近 3 条
            )

        # 策略调整建议
        strategy = self._suggest_strategy_adjustment(state, verification, failed_actions)

        # 本轮学到的经验
        lessons = self._extract_lessons(state, verification, failed_actions)

        return FeedbackReport(
            cycle_number=state.attempt,
            verification=verification,
            failed_actions=failed_actions,
            interface_changes=verification.diagnosis,
            improvement_suggestions=suggestions,
            strategy_adjustments=strategy,
            lessons_learned=lessons,
        )

    def _suggest_strategy_adjustment(
        self,
        state: LoopState,
        verification: VerificationResult,
        failed_actions: List[Dict],
    ) -> Dict:
        """
        建议策略调整

        根据失败模式，建议下一步怎么做。

        Args:
            state: 循环状态
            verification: 验证结果
            failed_actions: 失败的动作

        Returns:
            策略调整建议
        """
        adjustments = {
            "reduce_steps": False,       # 是否减少步骤
            "switch_engine": False,      # 是否切换引擎
            "add_wait": False,           # 是否增加等待
            "add_error_handling": False,  # 是否增加错误处理
            "change_approach": False,    # 是否完全换方法
            "simplified_goal": "",       # 简化后的目标
        }

        # 分析失败模式
        if len(failed_actions) > len(state.current_plan.steps) * 0.5:
            # 超过一半步骤失败，建议简化
            adjustments["reduce_steps"] = True
            adjustments["simplified_goal"] = self._simplify_goal(state.task)

        # 分析失败动作的错误类型
        for failed in failed_actions:
            error = failed.get("error", "").lower()
            if "timeout" in error or "等待" in error:
                adjustments["add_wait"] = True
            elif "element" in error or "控件" in error or "not found" in error:
                adjustments["switch_engine"] = True
            elif "permission" in error or "权限" in error:
                adjustments["add_error_handling"] = True

        # 如果连续多轮失败，完全换方法
        if state.attempt >= 3:
            adjustments["change_approach"] = True

        # 如果界面卡死，增加等待
        if verification.diagnosis.get("stuck_detected"):
            adjustments["add_wait"] = True

        return adjustments

    def _simplify_goal(self, task: str) -> str:
        """
        简化任务目标

        把复杂任务拆成更小的子目标。

        Args:
            task: 原始任务

        Returns:
            简化后的目标
        """
        if self.mimo:
            return self._simplify_with_mimo(task)
        return task  # 没有 AI 就返回原目标

    def _simplify_with_mimo(self, task: str) -> str:
        """用 MiMo 简化任务目标"""
        try:
            response = self.mimo.chat.completions.create(
                model="mimo-v2.5",
                messages=[
                    {
                        "role": "system",
                        "content": "把复杂任务简化成一个最小的可执行子目标。只返回简化后的目标文本，不要解释。",
                    },
                    {"role": "user", "content": f"把以下任务简化成最小步骤:\n{task}"},
                ],
                max_completion_tokens=512,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return task

    def _extract_lessons(
        self,
        state: LoopState,
        verification: VerificationResult,
        failed_actions: List[Dict],
    ) -> List[str]:
        """
        提取本轮学到的经验

        Args:
            state: 循环状态
            verification: 验证结果
            failed_actions: 失败的动作

        Returns:
            经验列表
        """
        lessons = []

        # 失败动作的共性
        if failed_actions:
            action_types = [a.get("type", "unknown") for a in failed_actions]
            if len(set(action_types)) == 1:
                lessons.append(f"操作类型 [{action_types[0]}] 在本轮全部失败，下次避免使用")

        # 界面状态的发现
        if verification.diagnosis.get("error_dialog_detected"):
            lessons.append("任务执行前需要先关闭错误弹窗")

        if verification.diagnosis.get("stuck_detected"):
            lessons.append("界面可能需要更长的响应时间")

        # 多轮重试的总结
        if state.attempt >= 3:
            lessons.append(f"已重试 {state.attempt} 次，需要改变策略")

        return lessons

    # ============================================================
    # 自动降级重规划
    # ============================================================

    def _fallback_replan(
        self,
        task: str,
        state: LoopState,
        verification: VerificationResult,
    ) -> Optional[TaskPlan]:
        """
        自动降级重规划（没有回调函数时使用）

        策略：
        1. 第 1 次失败：增加等待时间
        2. 第 2 次失败：简化任务步骤
        3. 第 3 次失败：换执行引擎
        4. 第 4 次失败：完全重新规划

        Args:
            task: 用户任务
            state: 循环状态
            verification: 验证结果

        Returns:
            新的执行计划，或 None（无法生成）
        """
        attempt = state.attempt

        if attempt == 1:
            # 第 1 次失败：在现有计划前加等待
            return self._add_pre_wait(state.current_plan)

        elif attempt == 2:
            # 第 2 次失败：简化步骤
            return self._simplify_plan(state.current_plan)

        elif attempt == 3:
            # 第 3 次失败：切换引擎（如果有 AI）
            if self.mimo:
                return self._replan_with_mimo(task, verification)
            return self._simplify_plan(state.current_plan)

        else:
            # 第 4+ 次失败：完全重新规划（如果有 AI）
            if self.mimo:
                return self._replan_with_mimo(task, verification)
            return None

    def _add_pre_wait(self, plan: TaskPlan) -> TaskPlan:
        """在计划开头加一个等待步骤"""
        wait_action = Action(
            action_type=ActionType.WAIT,
            params={"seconds": 2},
            description="等待界面稳定",
        )
        new_steps = [wait_action] + plan.steps
        new_plan = TaskPlan(
            goal=plan.goal,
            steps=new_steps,
            requires_screenshot=plan.requires_screenshot,
            max_retries=plan.max_retries,
        )
        return new_plan

    def _simplify_plan(self, plan: TaskPlan) -> TaskPlan:
        """
        简化计划（只保留前 3 个步骤）

        如果计划太复杂导致失败，先试最简单的。
        """
        simplified_steps = plan.steps[:3] if len(plan.steps) > 3 else plan.steps
        return TaskPlan(
            goal=plan.goal,
            steps=simplified_steps,
            requires_screenshot=plan.requires_screenshot,
            max_retries=plan.max_retries,
        )

    def _replan_with_mimo(self, task: str, verification: VerificationResult) -> Optional[TaskPlan]:
        """
        用 MiMo 重新规划

        把之前的失败经验和当前界面状态一起告诉 MiMo，让它重新规划。

        Args:
            task: 用户任务
            verification: 验证结果

        Returns:
            新的执行计划，或 None
        """
        # 构建包含失败经验的 prompt
        feedback_text = "\n".join([
            f"- 原因: {verification.reason}",
            f"- 建议: {verification.suggestion}",
        ])

        uia_tree = self._get_uia_tree()
        screenshot = self._take_screenshot()

        prompt = f"""之前的执行失败了，请重新规划。

## 用户任务
{task}

## 之前失败的原因
{feedback_text}

## 当前界面（UIA 控件树）
{uia_tree}

## 要求
1. 避开之前失败的方式
2. 尽量简化步骤
3. 返回 JSON 格式的执行计划

## 返回 JSON 格式
{{
    "analysis": "界面分析 + 失败原因分析",
    "adjusted_strategy": "调整后的策略",
    "steps": [
        {{
            "action": "操作类型",
            "params": {{}},
            "description": "描述"
        }}
    ],
    "requires_screenshot": true
}}
"""

        try:
            messages = [
                {"role": "system", "content": "你是 MI Hands 桌面自动化助手。之前的执行失败了，请根据失败原因重新规划。返回 JSON 格式。"},
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

            response = self.mimo.chat.completions.create(
                model="mimo-v2.5",
                messages=messages,
                max_completion_tokens=4096,
            )

            content = response.choices[0].message.content
            return self._parse_plan_from_response(task, content)

        except Exception as e:
            print(f"MiMo 重新规划失败: {e}")
            return None

    # ============================================================
    # 辅助方法
    # ============================================================

    def _take_screenshot(self) -> str:
        """截图（返回 base64）"""
        if self.vision:
            try:
                screenshot = self.vision.take_screenshot()
                if screenshot and hasattr(screenshot, "base64_data"):
                    return screenshot.base64_data
            except Exception as e:
                print(f"截图失败: {e}")
        return ""

    def _get_uia_tree(self) -> str:
        """获取 UIA 树"""
        if self.vision:
            try:
                return self.vision.get_snapshot()
            except Exception as e:
                print(f"获取 UIA 树失败: {e}")
        return ""

    def _judge_with_mimo(self, task: str, screenshot: str, uia_tree: str) -> Dict:
        """用 MiMo 判断任务是否完成"""
        try:
            from .retry_utils import retry_call

            def _make_api_call():
                messages = [
                    {
                        "role": "system",
                        "content": "你是 MI Hands 验证助手。判断任务是否完成。返回 JSON 格式。",
                    },
                    {
                        "role": "user",
                        "content": f"判断任务是否已完成。\n\n任务: {task}\n\n当前界面（UIA 控件树）:\n{uia_tree}",
                    },
                ]

                if screenshot:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "当前界面截图："},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}},
                        ],
                    })

                response = self.mimo.chat.completions.create(
                    model="mimo-v2.5",
                    messages=messages,
                    max_completion_tokens=2048,
                )

                content = response.choices[0].message.content
                json_content = self._extract_json(content)
                if not json_content:
                    return {"completed": False, "reason": "无法解析验证结果"}
                return json.loads(json_content)

            return retry_call(_make_api_call, max_retries=2, base_delay=1.0)
        except Exception as e:
            return {"completed": False, "reason": f"验证失败: {e}"}

    def _judge_fallback(self, task: str, uia_tree: str) -> Dict:
        """降级判断（不调用 AI）"""
        if uia_tree and "error" not in uia_tree.lower():
            return {"completed": True, "reason": "界面已更新（降级判断）"}
        return {"completed": False, "reason": "无法判断（降级模式）"}

    def _collect_failed_actions(self, result: TaskResult) -> List[Dict]:
        """从执行结果中收集失败的动作"""
        failed = []
        for ar in result.action_results:
            if not ar.success:
                failed.append({
                    "type": ar.action.action_type.value,
                    "description": ar.action.description,
                    "error": ar.message,
                    "params": ar.action.params,
                })
        return failed

    def _summarize_plan(self, plan: TaskPlan) -> str:
        """把计划摘要成简短文本"""
        if not plan:
            return "无计划"
        steps_desc = [s.description or s.action_type.value for s in plan.steps[:5]]
        return f"目标: {plan.goal} | 步骤: {', '.join(steps_desc)}"

    def _parse_plan_from_response(self, task: str, response: str) -> Optional[TaskPlan]:
        """从 MiMo 响应中解析出 TaskPlan"""
        json_content = self._extract_json(response)
        if not json_content:
            return None

        try:
            data = json.loads(json_content)
        except json.JSONDecodeError:
            return None

        plan = TaskPlan(goal=task)
        for step in data.get("steps", []):
            try:
                action = Action(
                    action_type=ActionType(step["action"]),
                    params=step,
                    description=step.get("description", ""),
                    target_index=step.get("index", -1),
                )
                plan.add_step(action)
            except (ValueError, KeyError):
                continue

        plan.requires_screenshot = data.get("requires_screenshot", True)
        return plan if plan.steps else None

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON（和 VerifyLayer 相同的鲁棒性逻辑）"""
        import re

        if not text:
            return ""

        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r"```json\s*\n(.*?)\n\s*```",
            r"```\s*\n(.*?)\n\s*```",
            r"\{[^{}]*\}",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_brace_start = text.rfind("{")
        last_brace_end = text.rfind("}")
        if last_brace_start != -1 and last_brace_end > last_brace_start:
            candidate = text[last_brace_start : last_brace_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return ""

    # ============================================================
    # 记录和统计
    # ============================================================

    def _on_task_complete(self, state: LoopState, result: TaskResult):
        """任务完成后的处理"""
        elapsed = time.time() - state.start_time

        # 记录到反思系统
        self.reflection.record_success(
            action="learning_loop",
            result={
                "task": state.task,
                "attempts": state.attempt,
                "elapsed": elapsed,
            },
        )

        # 记录循环历史
        self.loop_history.append({
            "task": state.task,
            "success": True,
            "attempts": state.attempt,
            "elapsed": elapsed,
            "history": state.history,
            "timestamp": datetime.now().isoformat(),
        })

    def _record_failure(self, task: str, verification: VerificationResult, failed_actions: List[Dict]):
        """记录失败到反思系统"""
        for failed in failed_actions:
            self.reflection.record_error(
                action=failed.get("type", "unknown"),
                error=failed.get("error", "unknown"),
                context={"task": task, "attempt": self._current_attempt},
                fix=verification.suggestion,
            )

        # 记录到循环历史
        self.loop_history.append({
            "task": task,
            "success": False,
            "reason": verification.reason,
            "suggestion": verification.suggestion,
            "failed_actions": [a.get("type") for a in failed_actions],
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def _current_attempt(self) -> int:
        """获取当前尝试次数（用于记录）"""
        return len(self.loop_history)

    def get_loop_stats(self) -> Dict:
        """获取学习循环统计"""
        total = len(self.loop_history)
        successes = sum(1 for h in self.loop_history if h.get("success"))

        return {
            "total_tasks": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0,
            "reflection_stats": self.reflection.get_stats(),
        }

    def get_loop_history(self, limit: int = 10) -> List[Dict]:
        """获取最近的循环历史"""
        return self.loop_history[-limit:]


# ============================================================
# 模拟执行（测试用）
# ============================================================

def _mock_execute(action: Action) -> ActionResult:
    """
    模拟执行一个动作（用于测试或没有执行器时）

    Args:
        action: 要模拟执行的动作

    Returns:
        模拟的执行结果
    """
    return ActionResult(
        action=action,
        success=True,
        message=f"[模拟] {action.action_type.value}: {action.description}",
    )
