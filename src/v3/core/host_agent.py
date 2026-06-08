"""
HostAgent - 决策层

职责：
1. 理解用户任务
2. 获取当前界面状态（UIA 树 + 截图）
3. 规划执行步骤
4. 输出 TaskPlan
5. 智能选择执行方案（实体操作 vs 坐标操作）

参考 UFO 的 HostAgent 设计，专注于 MiMo 视觉模型
借鉴 desktop-touch-mcp 的实体操作理念
"""

import json
from .action_models import Action, TaskPlan, ActionType
from .skill_manager import SkillManager
from .retry_utils import retry_call
from .experience_manager import ExperienceManager


class HostAgent:
    """
    决策层 - 理解任务，规划步骤

    流程：
    1. 接收用户任务
    2. 匹配本地 skill（如果有）
    3. 搜索相似任务的成功经验（自进化）
    4. 获取 UIA 树 + 截图
    5. 调用 MiMo 规划（注入 skill + 经验 prompt）
    6. 返回 TaskPlan
    """

    def __init__(self, mimo_client=None, experience_manager=None):
        """
        初始化决策层

        Args:
            mimo_client: MiMo API 客户端
            experience_manager: 经验管理器（自进化系统）
        """
        self.mimo = mimo_client
        self.skill_manager = SkillManager()
        self.experience = experience_manager or ExperienceManager()

    def plan(self, task: str, uia_tree: str, screenshot_base64: str = "") -> TaskPlan:
        """
        规划任务执行步骤

        流程：
        1. 匹配本地 skill
        2. 搜索相似任务的成功经验（自进化）
        3. 构建 prompt（注入 skill + 经验）
        4. 调用 MiMo 规划（如果无经验可用）
        5. 返回 TaskPlan

        Args:
            task: 用户任务描述
            uia_tree: 当前界面的 UIA 树文本
            screenshot_base64: 截图的 base64 数据（可选）

        Returns:
            TaskPlan: 任务规划
        """
        # 1. 匹配本地 skill
        matching_skills = self.skill_manager.find_matching_skills(task)

        # 2. 搜索相似任务的成功经验（自进化系统）
        experience_advice = ""
        high_confidence_exp = None
        if self.experience:
            # 获取经验建议文本（注入 prompt）
            experience_advice = self.experience.get_task_advice(task)
            # 查找高置信度的成功经验（直接复用步骤）
            high_confidence_exp = self._find_reusable_experience(task)

        # 3. 如果有高置信度的成功经验，优先使用经验中的步骤
        if high_confidence_exp and high_confidence_exp.confidence >= 0.8:
            plan = self._plan_from_experience(task, high_confidence_exp)
            if plan.steps:
                print(f"[自进化] 使用历史经验: {high_confidence_exp.exp_id} "
                      f"(置信度: {high_confidence_exp.confidence:.0%}, "
                      f"复用次数: {high_confidence_exp.use_count})")
                return plan

        # 4. 构建 Prompt（注入 skill + 经验建议）
        prompt = self._build_planning_prompt(task, uia_tree, matching_skills, experience_advice)

        # 5. 调用 MiMo 规划
        if self.mimo:
            response = self._call_mimo(prompt, screenshot_base64)
        else:
            # 降级：简单规则匹配
            response = self._fallback_planning(task, uia_tree)

        # 6. 解析响应
        plan = self._parse_response(task, response)

        return plan

    def _find_reusable_experience(self, task: str):
        """
        查找可直接复用的高置信度成功经验

        Args:
            task: 当前任务描述

        Returns:
            最佳匹配经验，或 None
        """
        if not self.experience:
            return None
        return self.experience.get_best_experience(task)

    def _plan_from_experience(self, task: str, experience) -> TaskPlan:
        """
        直接从成功经验生成执行计划

        将经验中的步骤序列转换为 TaskPlan，供执行层使用。
        步骤会根据当前界面微调（如控件索引可能变化）。

        Args:
            task: 当前任务描述
            experience: 成功经验对象

        Returns:
            TaskPlan: 基于经验的执行计划
        """
        plan = TaskPlan(goal=task)
        plan.context["source"] = "experience"
        plan.context["experience_id"] = experience.exp_id
        plan.context["experience_confidence"] = experience.confidence

        for step in experience.steps:
            try:
                action_type = ActionType(step.action_type)
                action = Action(
                    action_type=action_type,
                    params=step.params.copy(),
                    description=step.description or f"[经验] {step.action_type}",
                    target_control=step.target_control,
                    target_index=step.params.get("index", -1),
                )
                plan.add_step(action)
            except (ValueError, KeyError):
                # 经验中的步骤类型不被支持，跳过
                continue

        plan.requires_screenshot = True
        return plan

    def _build_planning_prompt(self, task: str, uia_tree: str, matching_skills: list = None,
                               experience_advice: str = "") -> str:
        """
        构建规划 Prompt

        参考 UFO 的 AppAgentPrompter 设计
        加入智能方案选择逻辑 + Skill 注入
        """
        # 构建 skill prompt
        skill_section = ""
        if matching_skills:
            skill_section = "\n## 可用 Skills（优先使用）\n\n"
            for skill in matching_skills[:3]:  # 最多 3 个 skill
                skill_name = skill.get("name", "")
                skill_prompt = skill.get("prompt", "")
                skill_desc = skill.get("description", "")
                skill_section += f"### Skill: {skill_name}\n"
                skill_section += f"描述: {skill_desc}\n"
                skill_section += f"指导:\n{skill_prompt}\n\n"

        return f"""你是 MI Hands 桌面自动化助手。根据用户任务和当前界面，智能选择最优执行方案。
{skill_section}
{experience_advice}
## 用户任务
{task}

## 当前界面（UIA 控件树）
{uia_tree}

## 可用执行引擎

### 基础引擎
- pyautogui: 通用方案，简单操作（点击、输入、快捷键）
- win32api: 底层控制，精细操作（模拟压感、速度控制）
- uia: 控件操作，精准定位（通过控件属性，不依赖坐标）
- clipboard: 剪贴板输入（文字输入的备选方案）
- pil: 批量图片生成（几何图形、重复图案）

### 选择指导
- 点击按钮/链接 → 优先 uia（精准定位）
- 输入文字 → 优先 uia 或 clipboard（稳定）
- 画图/素描 → 优先 pyautogui 或 win32api（模拟压感）
- 浏览器操作 → 优先 cdp（如果可用）
- 批量生成 → 优先 pil（最快）

## 可用操作

## 可用操作

### 基础操作
- click(index): 点击控件
- double_click(index): 双击控件
- type_text(index, text): 输入文字
- press_key(key): 按键
- hotkey(keys): 组合键
- scroll(direction): 滚动
- wait(seconds): 等待

### 绘制操作（智能选择）
- draw_path(points, engine="pyautogui"): 手绘路径
  - engine="pyautogui": 使用 pyautogui，适合简单线条
  - engine="win32": 使用 Win32 API，可模拟压感
- draw_curve(start, end, control, engine): 贝塞尔曲线
- draw_circle(center, radius, engine): 圆形
- draw_batch(width, height, elements): 批量绘制（PIL）

## 返回 JSON 格式

每个步骤需要指定执行引擎（engine）：

{{
    "analysis": "界面分析",
    "selected_scheme": "A/B/C（选择的方案）",
    "scheme_reason": "选择原因",
    "steps": [
        {{
            "action": "click",
            "index": 5,
            "engine": "pyautogui",
            "description": "点击确定按钮"
        }},
        {{
            "action": "draw_path",
            "points": [[100,200], [150,250]],
            "engine": "win32",
            "speed_curve": "fast-slow-fast",
            "description": "画一条渐变线条"
        }},
        {{
            "action": "draw_batch",
            "width": 800,
            "height": 600,
            "elements": [...],
            "engine": "pil",
            "description": "批量生成图案"
        }}
    ],
    "requires_screenshot": true
}}
"""

    def _call_mimo(self, prompt: str, screenshot_base64: str = "") -> str:
        """
        调用 MiMo API（带重试机制）

        专注于 MiMo 视觉模型
        """
        def _make_api_call():
            messages = [
                {"role": "system", "content": "你是 MI Hands 桌面自动化助手，专注于分析界面并规划操作步骤。返回 JSON 格式。"},
                {"role": "user", "content": prompt}
            ]

            # 如果有截图，添加到消息中
            if screenshot_base64:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "当前界面截图："},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]
                })

            # 调用 MiMo API
            # 注意：MiMo API 使用 max_completion_tokens 而不是 max_tokens
            # max_completion_tokens 包含推理 token + 输出 token
            # mimo-v2.5 默认开启思考模式，需要足够大的 token 上限
            response = self.mimo.chat.completions.create(
                model="mimo-v2.5",
                messages=messages,
                max_completion_tokens=8192,
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
            print(f"MiMo API 调用失败（已重试 3 次）: {e}")
            return ""

    def _fallback_planning(self, task: str, uia_tree: str) -> str:
        """
        降级规划（不调用 AI）

        简单规则匹配
        """
        steps = []

        # 简单规则：如果任务包含"打开"，使用 Win+R
        if "打开" in task or "启动" in task:
            steps.append({"action": "hotkey", "keys": ["win", "r"], "description": "打开 Run 对话框"})
            steps.append({"action": "wait", "seconds": 0.5, "description": "等待对话框"})

        # 返回默认响应
        return json.dumps({
            "analysis": "使用降级规划（未调用 MiMo）",
            "steps": steps,
            "requires_screenshot": True
        }, ensure_ascii=False)

    def _parse_response(self, task: str, response: str) -> TaskPlan:
        """
        解析 MiMo 响应，转换成 TaskPlan（鲁棒性增强版）
        """
        plan = TaskPlan(goal=task)

        try:
            # 提取 JSON 内容（处理各种格式）
            json_content = self._extract_json(response)
            if not json_content:
                print("无法从响应中提取 JSON")
                return plan

            data = json.loads(json_content)

            # 解析步骤
            for step in data.get("steps", []):
                try:
                    action = Action(
                        action_type=ActionType(step["action"]),
                        params=step,
                        description=step.get("description", ""),
                        target_index=step.get("index", -1),
                    )
                    plan.add_step(action)
                except (ValueError, KeyError) as e:
                    print(f"跳过无效步骤: {e}")
                    continue

            # 设置是否需要截图
            plan.requires_screenshot = data.get("requires_screenshot", True)

        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
        except Exception as e:
            print(f"解析响应失败: {e}")

        return plan

    def _extract_json(self, text: str) -> str:
        """
        从文本中提取 JSON 内容（鲁棒性增强版）

        处理以下情况：
        1. 纯 JSON
        2. markdown 代码块包裹
        3. 带有思考过程的文本
        4. 多层嵌套的代码块
        """
        if not text:
            return ""

        # 1. 尝试直接解析
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        # 2. 尝试提取 ```json ... ``` 块
        import re
        # 匹配 ```json ... ``` 或 ``` ... ```
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
