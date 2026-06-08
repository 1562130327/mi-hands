"""
VerifyLayer - 验证层

职责：
1. 截图检查结果
2. AI 判断是否符合要求
3. 不合格？打回重做，返回详细改进建议
4. 合格？任务完成
5. 持续感知：边操作边看（借鉴 cellar Cortex）
6. 集成 SmartVerifyLayer 的智能诊断能力

专注于 MiMo 视觉模型
"""

import json
from typing import Dict, Optional
from .action_models import TaskPlan, TaskResult
from .continuous_awareness import ContinuousAwareness
from .retry_utils import retry_call


class VerifyLayer:
    """
    验证层 - 检查任务是否完成

    流程：
    1. 截图
    2. 发给 MiMo 判断
    3. 不合格？返回改进建议
    4. 合格？返回成功

    新增能力：
    - 集成 SmartVerifyLayer 进行深度诊断
    - 验证失败时返回详细改进建议
    - 将验证结果传递给 learning_loop

    新增：持续感知（借鉴 cellar Cortex）
    - 边操作边看
    - 检测界面变化
    - 发现意外副作用
    """

    def __init__(self, mimo_client=None, vision_engine=None, smart_verify=None):
        """
        初始化验证层

        Args:
            mimo_client: MiMo API 客户端
            vision_engine: 视觉引擎（用于截图）
            smart_verify: SmartVerifyLayer 实例（可选，启用深度诊断）
        """
        self.mimo = mimo_client
        self.vision = vision_engine
        self.awareness = ContinuousAwareness(vision_engine)
        self.smart_verify = smart_verify

    def verify(self, task: str, plan: TaskPlan, max_retries: int = 3,
               before_snapshot: dict = None, action_results: list = None) -> TaskResult:
        """
        验证任务是否完成

        增强版：
        - 如果有 SmartVerifyLayer，使用深度诊断
        - 失败时返回详细改进建议（suggestions 字段）
        - 结果可用于 learning_loop 反馈

        Args:
            task: 用户任务
            plan: 任务规划
            max_retries: 最大重试次数
            before_snapshot: 操作前快照（可选，用于 SmartVerify 对比）
            action_results: 已执行操作的结果列表（可选）

        Returns:
            TaskResult: 任务结果（包含改进建议）
        """
        # 优先使用 SmartVerifyLayer 做深度验证
        if self.smart_verify:
            return self._verify_with_smart(task, plan, before_snapshot,
                                           action_results, max_retries)

        result = TaskResult(
            goal=task,
            success=False,
            steps_total=len(plan.steps),
        )

        for attempt in range(max_retries):
            # 获取当前状态
            screenshot = self._take_screenshot()
            uia_tree = self._get_uia_tree()

            # AI 判断
            if self.mimo:
                judgment = self._judge_with_mimo(task, screenshot, uia_tree)
            else:
                judgment = self._judge_fallback(task, uia_tree)

            # 更新结果
            result.retries = attempt + 1

            if judgment.get("completed", False):
                result.success = True
                result.message = "任务完成"
                return result
            else:
                result.message = judgment.get("reason", "任务未完成")
                # 收集改进建议
                suggestion = judgment.get("suggestion", "")
                if suggestion:
                    result.message += f" | 改进建议: {suggestion}"

        # 超过最大重试次数
        result.message = f"超过最大重试次数 ({max_retries})"
        return result

    def _verify_with_smart(self, task: str, plan: TaskPlan,
                           before_snapshot: dict = None,
                           action_results: list = None,
                           max_retries: int = 3) -> TaskResult:
        """
        使用 SmartVerifyLayer 做深度验证

        SmartVerifyLayer 提供：
        - 截图对比（操作前后对比）
        - UIA 树变化检测
        - 失败原因深度诊断
        - 0-100 完成度评分
        - 详细改进建议

        Args:
            task: 用户任务
            plan: 任务规划
            before_snapshot: 操作前快照
            action_results: 操作结果列表
            max_retries: 最大重试次数

        Returns:
            TaskResult: 包含详细改进建议的结果
        """
        from .smart_verify import VerifyStatus

        # 调用 SmartVerifyLayer 验证
        smart_result = self.smart_verify.verify(
            task=task,
            plan=plan,
            before_snapshot=before_snapshot,
            action_results=action_results,
            max_retries=max_retries,
        )

        # 转换为 TaskResult（兼容旧接口）
        result = TaskResult(
            goal=task,
            success=(smart_result.status == VerifyStatus.COMPLETED),
            steps_total=len(plan.steps),
        )

        # 构建详细消息（包含改进建议）
        msg_parts = []
        if smart_result.completion_score:
            msg_parts.append(f"完成度: {smart_result.completion_score.overall}/100")
            msg_parts.append(smart_result.completion_score.summary)

        if smart_result.failure_analysis:
            fa = smart_result.failure_analysis
            msg_parts.append(f"失败类型: {fa.failure_type.value}")
            msg_parts.append(f"根因: {fa.root_cause}")
            if fa.suggestions:
                msg_parts.append("改进建议:")
                for i, s in enumerate(fa.suggestions[:5], 1):
                    msg_parts.append(f"  {i}. {s}")
            result.message = " | ".join(msg_parts)
        elif smart_result.status == VerifyStatus.COMPLETED:
            result.message = "任务完成"
        else:
            result.message = smart_result.summary() if hasattr(smart_result, 'summary') else "验证完成"

        # 将失败诊断存入 result 的 action_results 方便 learning_loop 读取
        if smart_result.failure_analysis and action_results:
            result.action_results = action_results

        return result

    def get_improvement_suggestions(self, task: str) -> list:
        """
        获取当前界面的改进建议（供 learning_loop 使用）

        截图分析当前状态，返回具体的改进建议列表。

        Args:
            task: 用户任务

        Returns:
            改进建议列表
        """
        screenshot = self._take_screenshot()
        uia_tree = self._get_uia_tree()

        if self.mimo:
            judgment = self._judge_with_mimo(task, screenshot, uia_tree)
        else:
            judgment = self._judge_fallback(task, uia_tree)

        suggestions = []
        if judgment.get("suggestion"):
            suggestions.append(judgment["suggestion"])
        if judgment.get("reason"):
            suggestions.append(f"当前状态: {judgment['reason']}")

        return suggestions

    def _take_screenshot(self) -> str:
        """截图（返回 base64）"""
        if self.vision:
            try:
                screenshot = self.vision.take_screenshot()
                if screenshot and hasattr(screenshot, 'base64_data'):
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

    def _judge_with_mimo(self, task: str, screenshot: str, uia_tree: str) -> dict:
        """
        用 MiMo 判断任务是否完成（带重试机制）

        专注于 MiMo 视觉模型
        """
        def _make_api_call():
            prompt = f"""判断任务是否已完成。

## 任务
{task}

## 当前界面（UIA 控件树）
{uia_tree}

## 判断标准
1. 任务目标是否达成
2. 界面是否符合预期
3. 是否有错误提示

## 返回 JSON 格式
{{
    "completed": true/false,
    "reason": "判断原因",
    "suggestion": "改进建议（如果未完成）"
}}
"""

            messages = [
                {"role": "system", "content": "你是 MI Hands 验证助手，专注于判断任务是否完成。返回 JSON 格式。"},
                {"role": "user", "content": prompt}
            ]

            # 如果有截图，添加到消息中
            if screenshot:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "当前界面截图："},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}}
                    ]
                })

            # 调用 MiMo API
            response = self.mimo.chat.completions.create(
                model="mimo-v2.5",
                messages=messages,
                max_completion_tokens=2048,
            )

            content = response.choices[0].message.content

            # 提取 JSON（鲁棒性增强版）
            json_content = self._extract_json(content)
            if not json_content:
                return {"completed": False, "reason": "无法解析验证结果"}

            return json.loads(json_content)

        try:
            # 带重试的 API 调用
            return retry_call(
                _make_api_call,
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
            )
        except Exception as e:
            print(f"MiMo 验证失败（已重试 3 次）: {e}")
            return {"completed": False, "reason": f"验证失败: {e}"}

    def _judge_fallback(self, task: str, uia_tree: str) -> dict:
        """
        降级判断（不调用 AI）

        简单规则判断
        """
        # 简单规则：如果 UIA 树有内容，假设任务完成
        if uia_tree and "无法获取" not in uia_tree:
            return {"completed": True, "reason": "界面已更新"}

        return {"completed": False, "reason": "无法判断"}

    def _extract_json(self, text: str) -> str:
        """
        从文本中提取 JSON 内容（鲁棒性增强版）

        处理以下情况：
        1. 纯 JSON
        2. markdown 代码块包裹
        3. 带有思考过程的文本
        4. 多层嵌套的代码块
        """
        import re

        if not text:
            return ""

        # 1. 尝试直接解析
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        # 2. 尝试提取 ```json ... ``` 块
        patterns = [
            r'```json\s*\n(.*?)\n\s*```',  # ```json ... ```
            r'```\s*\n(.*?)\n\s*```',      # ``` ... ```
            r'\{[^{}]*\}',                  # 简单的 { ... }
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    # 尝试解析每个匹配
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        # 3. 尝试找到最后一个 { ... } 块（MiMo 可能在 JSON 前面输出思考过程）
        last_brace_start = text.rfind('{')
        last_brace_end = text.rfind('}')
        if last_brace_start != -1 and last_brace_end > last_brace_start:
            candidate = text[last_brace_start:last_brace_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return ""
