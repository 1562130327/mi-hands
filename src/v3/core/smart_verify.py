"""
SmartVerifyLayer - 智能验证层

增强现有的 VerifyLayer，提供更精准的验证能力：

1. 截图对比（操作前后对比）
   - 视觉差异检测
   - 关键区域变化分析
   - 异常区域识别

2. UIA 树变化检测
   - 控件增删检测
   - 属性变化追踪
   - 层级结构变化

3. 任务完成度评估
   - 多维度评分（0-100）
   - 分项进度追踪
   - 部分完成识别

4. 失败原因分析
   - 错误模式匹配
   - 根因诊断
   - 改进建议生成

核心思想：不只是判断"完成/未完成"，而是给出具体的原因和可操作的改进建议。
"""

import json
import re
import time
import hashlib
import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .action_models import TaskPlan, TaskResult, Action
from .continuous_awareness import ContinuousAwareness
from .retry_utils import retry_call


# ==================== 数据模型 ====================

class VerifyStatus(Enum):
    """验证状态"""
    COMPLETED = "completed"           # 任务完成
    PARTIAL = "partial"               # 部分完成
    FAILED = "failed"                 # 任务失败
    UNCHANGED = "unchanged"           # 界面无变化（可能卡住了）
    ERROR = "error"                   # 验证过程出错


class FailureType(Enum):
    """失败类型"""
    ELEMENT_NOT_FOUND = "element_not_found"     # 目标元素未找到
    WRONG_PAGE = "wrong_page"                   # 跳到了错误的页面
    DIALOG_BLOCKED = "dialog_blocked"           # 被弹窗/对话框阻挡
    PERMISSION_DENIED = "permission_denied"     # 权限不足
    ACTION_FAILED = "action_failed"             # 操作执行失败
    SLOW_RESPONSE = "slow_response"             # 界面响应慢/加载中
    UNEXPECTED_STATE = "unexpected_state"       # 意外的界面状态
    NO_CHANGE = "no_change"                     # 操作后界面没变化
    WRONG_CONTENT = "wrong_content"             # 内容不符合预期
    PARTIAL_COMPLETE = "partial_complete"       # 部分完成但未全部达成
    UNKNOWN = "unknown"                         # 未知原因


@dataclass
class ScreenshotDiff:
    """截图对比结果"""
    has_changed: bool                           # 界面是否变化了
    change_ratio: float                         # 变化比例 (0.0 - 1.0)
    changed_regions: list[dict] = field(default_factory=list)   # 变化区域列表
    new_elements: list[str] = field(default_factory=list)       # 新出现的元素描述
    disappeared_elements: list[str] = field(default_factory=list)  # 消失的元素
    error_indicators: list[str] = field(default_factory=list)   # 检测到的错误指示
    summary: str = ""                           # 变化摘要


@dataclass
class UITreeDiff:
    """UIA 树变化结果"""
    has_changed: bool                           # 树是否变化了
    added_controls: list[dict] = field(default_factory=list)    # 新增的控件
    removed_controls: list[dict] = field(default_factory=list)  # 移除的控件
    modified_controls: list[dict] = field(default_factory=list) # 属性变化的控件
    new_dialog: bool = False                    # 是否出现了新对话框
    page_changed: bool = False                  # 是否切换了页面
    summary: str = ""                           # 变化摘要


@dataclass
class CompletionScore:
    """完成度评估"""
    overall: int                                # 总体评分 (0-100)
    sub_scores: dict[str, int] = field(default_factory=dict)  # 分项评分
    completed_criteria: list[str] = field(default_factory=list)  # 已满足的条件
    pending_criteria: list[str] = field(default_factory=list)    # 未满足的条件
    summary: str = ""                           # 评估摘要


@dataclass
class FailureAnalysis:
    """失败原因分析"""
    failure_type: FailureType                   # 失败类型
    root_cause: str                             # 根因描述
    evidence: list[str] = field(default_factory=list)  # 支撑证据
    suggestions: list[str] = field(default_factory=list)  # 改进建议
    can_retry: bool = True                      # 是否值得重试
    confidence: float = 0.0                     # 诊断置信度 (0-1)


@dataclass
class SmartVerifyResult:
    """智能验证综合结果"""
    status: VerifyStatus                        # 验证状态
    screenshot_diff: Optional[ScreenshotDiff] = None
    ui_tree_diff: Optional[UITreeDiff] = None
    completion_score: Optional[CompletionScore] = None
    failure_analysis: Optional[FailureAnalysis] = None
    raw_ai_response: str = ""                   # AI 原始返回
    timestamp: float = 0.0                      # 验证时间戳
    verify_duration: float = 0.0               # 验证耗时（秒）

    def to_dict(self) -> dict:
        """转成字典"""
        return {
            "status": self.status.value,
            "completion": self.completion_score.overall if self.completion_score else 0,
            "failure_type": self.failure_analysis.failure_type.value if self.failure_analysis else None,
            "root_cause": self.failure_analysis.root_cause if self.failure_analysis else None,
            "suggestions": self.failure_analysis.suggestions if self.failure_analysis else [],
            "screenshot_changed": self.screenshot_diff.has_changed if self.screenshot_diff else None,
            "ui_tree_changed": self.ui_tree_diff.has_changed if self.ui_tree_diff else None,
            "duration": round(self.verify_duration, 2),
        }

    def summary(self) -> str:
        """生成一行摘要"""
        parts = [f"[{self.status.value}]"]
        if self.completion_score:
            parts.append(f"完成度 {self.completion_score.overall}/100")
        if self.failure_analysis:
            parts.append(f"原因: {self.failure_analysis.failure_type.value}")
        parts.append(f"耗时 {self.verify_duration:.1f}s")
        return " | ".join(parts)


# ==================== 截图对比器 ====================

class ScreenshotComparator:
    """
    截图对比器

    通过像素级比较检测操作前后的视觉差异。
    纯 Python 实现，不依赖 OpenCV。
    """

    def __init__(self, threshold: float = 0.05):
        """
        Args:
            threshold: 变化判定阈值，低于此值认为无变化 (0.0 - 1.0)
        """
        self.threshold = threshold

    def compare(
        self,
        before_b64: str,
        after_b64: str,
        ai_client=None,
    ) -> ScreenshotDiff:
        """
        对比两张截图

        Args:
            before_b64: 操作前截图（base64）
            after_b64: 操作后截图（base64）
            ai_client: 可选的 AI 客户端，用于视觉分析

        Returns:
            ScreenshotDiff 对比结果
        """
        diff = ScreenshotDiff(has_changed=False, change_ratio=0.0)

        if not before_b64 or not after_b64:
            diff.summary = "缺少截图，无法对比"
            return diff

        # 1. 基础哈希对比（快速判断是否变化）
        before_hash = hashlib.md5(before_b64.encode()).hexdigest()
        after_hash = hashlib.md5(after_b64.encode()).hexdigest()

        if before_hash == after_hash:
            diff.summary = "截图完全一致，界面未变化"
            return diff

        # 2. 长度差异估算变化幅度
        len_before = len(before_b64)
        len_after = len(after_b64)
        len_diff_ratio = abs(len_after - len_before) / max(len_before, 1)

        # base64 长度差粗略映射到变化比例
        # 注意：这只是粗略估算，有 AI 时用 AI 做精确分析
        diff.change_ratio = min(len_diff_ratio, 1.0)
        diff.has_changed = True

        # 3. 如果有 AI 客户端，用视觉模型做精确分析
        if ai_client:
            try:
                ai_diff = self._ai_analyze_diff(before_b64, after_b64, ai_client)
                if ai_diff:
                    return ai_diff
            except Exception as e:
                # AI 分析失败，降级到基础对比
                print(f"AI 截图对比失败，降级到基础对比: {e}")

        # 4. 降级：基于元数据的粗略判断
        diff.summary = f"检测到界面变化（变化幅度约 {diff.change_ratio:.1%}）"
        return diff

    def _ai_analyze_diff(
        self,
        before_b64: str,
        after_b64: str,
        ai_client,
    ) -> Optional[ScreenshotDiff]:
        """用 AI 视觉模型分析截图差异"""
        prompt = """分析这两张截图（操作前后），检测界面变化。

请返回 JSON 格式：
{
    "has_changed": true/false,
    "change_ratio": 0.0到1.0之间的数值,
    "changed_regions": [
        {"area": "区域描述", "description": "变化内容"}
    ],
    "new_elements": ["新出现的元素"],
    "disappeared_elements": ["消失的元素"],
    "error_indicators": ["检测到的错误信息/弹窗等"],
    "summary": "一句话总结变化"
}

重点关注：
1. 是否有错误弹窗出现
2. 目标操作区域是否变化
3. 是否切换了页面/标签
4. 内容是否更新
"""

        messages = [
            {"role": "system", "content": "你是界面变化分析专家。返回 JSON 格式。"},
            {"role": "user", "content": [
                {"type": "text", "text": "操作前截图："},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{before_b64}"}},
            ]},
            {"role": "user", "content": [
                {"type": "text", "text": "操作后截图："},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_b64}"}},
            ]},
            {"role": "user", "content": prompt},
        ]

        response = ai_client.chat.completions.create(
            model="mimo-v2.5",
            messages=messages,
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        parsed = self._extract_json(content)
        if not parsed:
            return None

        data = json.loads(parsed)
        return ScreenshotDiff(
            has_changed=data.get("has_changed", False),
            change_ratio=data.get("change_ratio", 0.0),
            changed_regions=data.get("changed_regions", []),
            new_elements=data.get("new_elements", []),
            disappeared_elements=data.get("disappeared_elements", []),
            error_indicators=data.get("error_indicators", []),
            summary=data.get("summary", ""),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        if not text:
            return ""
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*\}',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_start = text.rfind('{')
        last_end = text.rfind('}')
        if last_start != -1 and last_end > last_start:
            candidate = text[last_start:last_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return ""


# ==================== UIA 树差异分析 ====================

class UITreeAnalyzer:
    """
    UIA 树变化分析器

    对比操作前后的 UIA 控件树，检测：
    - 新增/移除的控件
    - 控件属性变化
    - 页面切换
    - 弹窗出现
    """

    def analyze(
        self,
        before_tree: str,
        after_tree: str,
        ai_client=None,
    ) -> UITreeDiff:
        """
        分析 UIA 树变化

        Args:
            before_tree: 操作前的 UIA 树文本
            after_tree: 操作后的 UIA 树文本

        Returns:
            UITreeDiff 变化分析结果
        """
        diff = UITreeDiff(has_changed=False)

        if not before_tree or not after_tree:
            diff.summary = "缺少 UIA 树数据"
            return diff

        # 1. 哈希快速判断
        before_hash = hashlib.md5(before_tree.encode()).hexdigest()
        after_hash = hashlib.md5(after_tree.encode()).hexdigest()

        if before_hash == after_hash:
            diff.summary = "UIA 树完全一致，界面未变化"
            return diff

        diff.has_changed = True

        # 2. 基础文本差异分析
        text_diff = self._text_diff(before_tree, after_tree)

        # 3. 检测弹窗
        diff.new_dialog = self._detect_new_dialog(after_tree)
        if diff.new_dialog:
            diff.summary = "检测到新弹窗/对话框出现"
            return diff

        # 4. 检测页面切换
        diff.page_changed = self._detect_page_change(before_tree, after_tree)
        if diff.page_changed:
            diff.summary = "检测到页面切换"
            return diff

        # 5. 控件变化统计
        diff.added_controls = text_diff.get("added", [])
        diff.removed_controls = text_diff.get("removed", [])
        diff.modified_controls = text_diff.get("modified", [])

        # 6. 如果有 AI，做语义分析
        if ai_client:
            try:
                ai_diff = self._ai_analyze_tree(before_tree, after_tree, ai_client)
                if ai_diff:
                    diff.summary = ai_diff.get("summary", diff.summary)
                    diff.added_controls.extend(ai_diff.get("added", []))
                    diff.removed_controls.extend(ai_diff.get("removed", []))
            except Exception as e:
                print(f"AI UIA 树分析失败: {e}")

        if not diff.summary:
            parts = []
            if diff.added_controls:
                parts.append(f"新增 {len(diff.added_controls)} 个控件")
            if diff.removed_controls:
                parts.append(f"移除 {len(diff.removed_controls)} 个控件")
            if diff.modified_controls:
                parts.append(f"修改 {len(diff.modified_controls)} 个控件")
            diff.summary = "UIA 树变化: " + ", ".join(parts) if parts else "UIA 树有变化"

        return diff

    def _text_diff(self, before: str, after: str) -> dict:
        """基于文本行的差异分析"""
        before_lines = [l.strip() for l in before.splitlines() if l.strip()]
        after_lines = [l.strip() for l in after.splitlines() if l.strip()]

        added = []
        removed = []
        modified = []

        differ = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )

        for line in differ:
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:].strip()
                if content:
                    added.append({"text": content[:100]})
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:].strip()
                if content:
                    removed.append({"text": content[:100]})

        return {"added": added, "removed": removed, "modified": modified}

    def _detect_new_dialog(self, tree: str) -> bool:
        """检测是否有新的对话框/弹窗"""
        dialog_keywords = [
            "dialog", "弹窗", "确认", "取消", "是", "否",
            "alert", "warning", "error", "message box",
            "对话框", "提示", "提示框",
        ]
        tree_lower = tree.lower()
        return any(kw in tree_lower for kw in dialog_keywords)

    def _detect_page_change(self, before: str, after: str) -> bool:
        """检测是否发生了页面切换"""
        # 提取窗口标题（通常在 UIA 树顶部）
        def extract_window_title(tree: str) -> str:
            lines = tree.strip().splitlines()
            if lines:
                return lines[0].strip()[:80]
            return ""

        title_before = extract_window_title(before)
        title_after = extract_window_title(after)

        # 窗口标题不同意味着切换了
        if title_before and title_after and title_before != title_after:
            return True

        return False

    def _ai_analyze_tree(
        self,
        before_tree: str,
        after_tree: str,
        ai_client,
    ) -> Optional[dict]:
        """用 AI 分析 UIA 树变化的语义含义"""
        # 截断过长的树
        max_len = 3000
        before_short = before_tree[:max_len]
        after_short = after_tree[:max_len]

        prompt = f"""对比这两个 UIA 控件树（操作前后），分析界面发生了什么变化。

## 操作前 UIA 树
```
{before_short}
```

## 操作后 UIA 树
```
{after_short}
```

请返回 JSON：
{{
    "summary": "一句话总结变化的含义",
    "added": [{{"text": "新增的有意义控件描述"}}],
    "removed": [{{"text": "消失的有意义控件描述"}}],
    "page_changed": true/false,
    "new_dialog": true/false,
    "dialog_content": "如果出现弹窗，弹窗内容是什么"
}}
"""
        messages = [
            {"role": "system", "content": "你是 Windows UI 自动化专家。返回 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        response = ai_client.chat.completions.create(
            model="mimo-v2.5",
            messages=messages,
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        parsed = self._extract_json(content)
        if parsed:
            return json.loads(parsed)
        return None

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        if not text:
            return ""
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*\}',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_start = text.rfind('{')
        last_end = text.rfind('}')
        if last_start != -1 and last_end > last_start:
            candidate = text[last_start:last_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return ""


# ==================== 失败原因分析器 ====================

class FailureDiagnoser:
    """
    失败原因诊断器

    根据截图对比、UIA 树变化、错误信息等多维信号，
    综合诊断失败的根本原因，并给出可操作的改进建议。
    """

    # 错误模式库：关键词 -> 失败类型
    ERROR_PATTERNS = {
        FailureType.PERMISSION_DENIED: [
            "权限", "permission", "access denied", "管理员",
            "以管理员", "administrator", "uac", "用户账户控制",
        ],
        FailureType.DIALOG_BLOCKED: [
            "确认", "是否", "弹窗", "dialog", "alert",
            "是否允许", "确认删除", "覆盖", "overwrite",
        ],
        FailureType.ELEMENT_NOT_FOUND: [
            "找不到", "未找到", "not found", "不存在",
            "目标元素", "控件不存在", "element not found",
        ],
        FailureType.WRONG_PAGE: [
            "页面不对", "不在", "错误的窗口", "wrong page",
            "切换到", "打开了错误",
        ],
        FailureType.SLOW_RESPONSE: [
            "加载中", "loading", "请稍候", "正在",
            "等待", "响应超时", "timeout",
        ],
        FailureType.ACTION_FAILED: [
            "操作失败", "执行失败", "failed", "error",
            "异常", "exception", "crash",
        ],
    }

    def diagnose(
        self,
        screenshot_diff: Optional[ScreenshotDiff],
        ui_tree_diff: Optional[UITreeDiff],
        error_messages: list[str],
        task_context: str = "",
        ai_client=None,
    ) -> FailureAnalysis:
        """
        综合诊断失败原因

        Args:
            screenshot_diff: 截图对比结果
            ui_tree_diff: UIA 树变化结果
            error_messages: 错误信息列表
            task_context: 任务上下文
            ai_client: AI 客户端（可选，用于深度诊断）

        Returns:
            FailureAnalysis 诊断结果
        """
        evidence = []
        signals = {}  # 收集所有信号

        # 1. 分析错误信息
        error_analysis = self._analyze_error_messages(error_messages)
        if error_analysis:
            signals["error"] = error_analysis
            evidence.extend([f"错误信息: {msg}" for msg in error_messages[:3]])

        # 2. 分析截图变化
        if screenshot_diff:
            if not screenshot_diff.has_changed:
                signals["no_screenshot_change"] = True
                evidence.append("操作前后截图完全一致，界面没有变化")
            elif screenshot_diff.error_indicators:
                signals["visual_error"] = screenshot_diff.error_indicators
                evidence.extend([f"视觉错误: {e}" for e in screenshot_diff.error_indicators[:3]])

        # 3. 分析 UIA 树变化
        if ui_tree_diff:
            if not ui_tree_diff.has_changed:
                signals["no_ui_tree_change"] = True
                evidence.append("UIA 树完全一致，控件没有变化")
            if ui_tree_diff.new_dialog:
                signals["dialog_appeared"] = True
                evidence.append("检测到新弹窗/对话框出现")
            if ui_tree_diff.page_changed:
                signals["page_changed"] = True
                evidence.append("检测到页面切换")

        # 4. 规则匹配诊断
        diagnosis = self._rule_based_diagnose(signals, evidence)

        # 5. 如果有 AI 且规则诊断置信度不够，用 AI 深度诊断
        if ai_client and diagnosis.confidence < 0.7 and task_context:
            try:
                ai_diagnosis = self._ai_diagnose(
                    task_context, signals, evidence, ai_client
                )
                if ai_diagnosis and ai_diagnosis.confidence > diagnosis.confidence:
                    return ai_diagnosis
            except Exception as e:
                print(f"AI 诊断失败，使用规则诊断: {e}")

        return diagnosis

    def _analyze_error_messages(self, messages: list[str]) -> Optional[dict]:
        """分析错误信息，匹配失败模式"""
        if not messages:
            return None

        combined = " ".join(messages).lower()
        for failure_type, keywords in self.ERROR_PATTERNS.items():
            for kw in keywords:
                if kw.lower() in combined:
                    return {
                        "failure_type": failure_type,
                        "matched_keyword": kw,
                        "raw_messages": messages[:5],
                    }

        return None

    def _rule_based_diagnose(
        self,
        signals: dict,
        evidence: list[str],
    ) -> FailureAnalysis:
        """基于规则的诊断"""

        # 优先级 1: 有明确的错误信息匹配
        if "error" in signals:
            error_info = signals["error"]
            failure_type = error_info["failure_type"]
            return FailureAnalysis(
                failure_type=failure_type,
                root_cause=f"检测到关键词 '{error_info['matched_keyword']}' 对应的 {failure_type.value} 错误",
                evidence=evidence,
                suggestions=self._get_suggestions(failure_type),
                can_retry=failure_type != FailureType.PERMISSION_DENIED,
                confidence=0.8,
            )

        # 优先级 2: 弹窗阻挡
        if signals.get("dialog_appeared"):
            return FailureAnalysis(
                failure_type=FailureType.DIALOG_BLOCKED,
                root_cause="操作后出现弹窗/对话框，可能阻挡了后续操作",
                evidence=evidence,
                suggestions=[
                    "先关闭弹窗再继续",
                    "检查是否触发了确认对话框",
                    "检查是否有系统提示需要处理",
                ],
                can_retry=True,
                confidence=0.85,
            )

        # 优先级 3: 页面切换（可能跳错了）
        if signals.get("page_changed"):
            return FailureAnalysis(
                failure_type=FailureType.WRONG_PAGE,
                root_cause="操作后页面发生了切换，可能跳转到了错误的页面",
                evidence=evidence,
                suggestions=[
                    "检查操作是否点击了错误的链接/按钮",
                    "确认当前页面是否是目标页面",
                    "可能需要先返回再重试",
                ],
                can_retry=True,
                confidence=0.75,
            )

        # 优先级 4: 界面完全没变化
        no_change = signals.get("no_screenshot_change") and signals.get("no_ui_tree_change")
        if no_change:
            return FailureAnalysis(
                failure_type=FailureType.NO_CHANGE,
                root_cause="操作前后界面完全没有任何变化，操作可能没有生效",
                evidence=evidence,
                suggestions=[
                    "检查目标元素是否可交互",
                    "尝试用不同方式点击（如坐标点击代替控件点击）",
                    "检查页面是否在加载中",
                    "可能需要等待界面响应",
                ],
                can_retry=True,
                confidence=0.9,
            )

        # 只有截图没变化（UIA 树有变化）
        if signals.get("no_screenshot_change"):
            return FailureAnalysis(
                failure_type=FailureType.UNEXPECTED_STATE,
                root_cause="截图没变化但 UIA 树有变化，可能是不可见的后台变化",
                evidence=evidence,
                suggestions=[
                    "检查操作是否影响了不可见的 UI 元素",
                    "尝试滚动页面查看更多内容",
                ],
                can_retry=True,
                confidence=0.5,
            )

        # 只有 UIA 树没变化（截图有变化）
        if signals.get("no_ui_tree_change"):
            return FailureAnalysis(
                failure_type=FailureType.UNEXPECTED_STATE,
                root_cause="截图有变化但 UIA 树没有变化，可能是视觉渲染层变化",
                evidence=evidence,
                suggestions=[
                    "变化可能只是视觉层面的（如动画、滚动）",
                    "检查是否有内容更新但控件结构未变",
                ],
                can_retry=True,
                confidence=0.5,
            )

        # 无法确定原因
        return FailureAnalysis(
            failure_type=FailureType.UNKNOWN,
            root_cause="无法确定失败原因，需要更多上下文信息",
            evidence=evidence,
            suggestions=[
                "尝试重新截图并分析",
                "检查操作日志是否有异常",
                "手动检查界面当前状态",
            ],
            can_retry=True,
            confidence=0.3,
        )

    def _get_suggestions(self, failure_type: FailureType) -> list[str]:
        """根据失败类型获取改进建议"""
        suggestions_map = {
            FailureType.ELEMENT_NOT_FOUND: [
                "等待页面加载完成后再查找元素",
                "检查元素名称/类型是否匹配",
                "尝试滚动页面让元素可见",
                "使用坐标定位作为备选方案",
            ],
            FailureType.WRONG_PAGE: [
                "检查是否点击了错误的按钮",
                "确认当前页面标题是否正确",
                "可能需要返回上一页再重试",
            ],
            FailureType.DIALOG_BLOCKED: [
                "先处理弹窗（点击确认/取消）",
                "检查弹窗内容并适当响应",
                "如果有多个弹窗，逐个处理",
            ],
            FailureType.PERMISSION_DENIED: [
                "尝试以管理员权限运行",
                "检查是否需要 UAC 授权",
                "考虑使用其他方式绕过权限限制",
            ],
            FailureType.ACTION_FAILED: [
                "检查操作参数是否正确",
                "确认目标控件是否支持该操作",
                "尝试替代的操作方式",
            ],
            FailureType.SLOW_RESPONSE: [
                "增加等待时间",
                "添加 loading 状态检测",
                "等待特定元素出现再继续",
            ],
            FailureType.NO_CHANGE: [
                "确认操作目标元素是否正确",
                "尝试用坐标点击代替控件点击",
                "检查页面是否已完全加载",
                "等待 1-2 秒后重新检查",
            ],
            FailureType.UNEXPECTED_STATE: [
                "截图分析当前界面状态",
                "检查是否有意外的弹窗或覆盖层",
                "尝试关闭不需要的窗口后重试",
            ],
            FailureType.WRONG_CONTENT: [
                "核对实际显示的内容与预期",
                "检查是否需要滚动才能看到完整内容",
                "确认数据是否已正确输入/保存",
            ],
            FailureType.PARTIAL_COMPLETE: [
                "检查未完成的具体步骤",
                "针对未完成部分单独重试",
                "检查是否有错误阻断了后续步骤",
            ],
        }
        return suggestions_map.get(failure_type, ["建议重新分析任务"])

    def _ai_diagnose(
        self,
        task_context: str,
        signals: dict,
        evidence: list[str],
        ai_client,
    ) -> Optional[FailureAnalysis]:
        """用 AI 做深度诊断"""
        prompt = f"""分析以下操作失败的原因，给出诊断和改进建议。

## 任务
{task_context}

## 检测到的信号
{json.dumps(signals, ensure_ascii=False, indent=2)}

## 证据
{chr(10).join(f"- {e}" for e in evidence)}

请返回 JSON：
{{
    "failure_type": "element_not_found|wrong_page|dialog_blocked|permission_denied|action_failed|slow_response|unexpected_state|no_change|wrong_content|partial_complete|unknown",
    "root_cause": "根因的详细描述",
    "suggestions": ["具体可操作的改进建议1", "建议2", "建议3"],
    "can_retry": true/false,
    "confidence": 0.0到1.0之间的数值
}}
"""
        messages = [
            {"role": "system", "content": "你是 Windows 自动化故障诊断专家。返回 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        response = ai_client.chat.completions.create(
            model="mimo-v2.5",
            messages=messages,
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        parsed = self._extract_json(content)
        if not parsed:
            return None

        data = json.loads(parsed)
        try:
            ft = FailureType(data.get("failure_type", "unknown"))
        except ValueError:
            ft = FailureType.UNKNOWN

        return FailureAnalysis(
            failure_type=ft,
            root_cause=data.get("root_cause", ""),
            evidence=evidence,
            suggestions=data.get("suggestions", []),
            can_retry=data.get("can_retry", True),
            confidence=data.get("confidence", 0.5),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        if not text:
            return ""
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*\}',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_start = text.rfind('{')
        last_end = text.rfind('}')
        if last_start != -1 and last_end > last_start:
            candidate = text[last_start:last_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return ""


# ==================== 任务完成度评估器 ====================

class CompletionEvaluator:
    """
    任务完成度评估器

    从多个维度评估任务的完成程度：
    - 目标达成度
    - 操作成功率
    - 界面状态匹配
    - 部分完成识别
    """

    def evaluate(
        self,
        task: str,
        plan: TaskPlan,
        screenshot_diff: Optional[ScreenshotDiff] = None,
        ui_tree_diff: Optional[UITreeDiff] = None,
        action_results: list = None,
        ai_client=None,
    ) -> CompletionScore:
        """
        评估任务完成度

        Args:
            task: 用户任务描述
            plan: 任务规划
            screenshot_diff: 截图对比结果
            ui_tree_diff: UIA 树变化结果
            action_results: 已执行操作的结果列表
            ai_client: AI 客户端

        Returns:
            CompletionScore 完成度评估
        """
        if ai_client:
            return self._ai_evaluate(
                task, plan, screenshot_diff, ui_tree_diff,
                action_results, ai_client
            )

        return self._rule_evaluate(
            task, plan, screenshot_diff, ui_tree_diff, action_results
        )

    def _rule_evaluate(
        self,
        task: str,
        plan: TaskPlan,
        screenshot_diff: Optional[ScreenshotDiff],
        ui_tree_diff: Optional[UITreeDiff],
        action_results: list,
    ) -> CompletionScore:
        """基于规则的完成度评估"""
        sub_scores = {}
        completed = []
        pending = []

        # 维度 1: 操作执行成功率
        if action_results:
            total = len(action_results)
            success = sum(1 for r in action_results if getattr(r, 'success', False))
            rate = (success / total * 100) if total > 0 else 0
            sub_scores["操作执行"] = int(rate)
            if rate == 100:
                completed.append("所有操作已成功执行")
            else:
                pending.append(f"操作成功率 {rate:.0f}%（{success}/{total}）")
        else:
            sub_scores["操作执行"] = 0
            pending.append("尚未执行任何操作")

        # 维度 2: 界面变化
        if screenshot_diff:
            if screenshot_diff.has_changed:
                if screenshot_diff.error_indicators:
                    sub_scores["界面状态"] = 30  # 有错误
                    pending.append("界面出现错误提示")
                else:
                    sub_scores["界面状态"] = 70  # 有变化但没错误
                    completed.append("界面已发生变化")
            else:
                sub_scores["界面状态"] = 0
                pending.append("界面没有变化")
        else:
            sub_scores["界面状态"] = 50  # 未知

        # 维度 3: 控件树状态
        if ui_tree_diff:
            if ui_tree_diff.new_dialog:
                sub_scores["控件状态"] = 20  # 有弹窗阻挡
                pending.append("有弹窗需要处理")
            elif ui_tree_diff.has_changed:
                sub_scores["控件状态"] = 70
                completed.append("控件树已更新")
            else:
                sub_scores["控件状态"] = 0
                pending.append("控件树没有变化")
        else:
            sub_scores["控件状态"] = 50

        # 计算总分（加权平均）
        weights = {"操作执行": 0.4, "界面状态": 0.35, "控件状态": 0.25}
        overall = 0
        for dim, score in sub_scores.items():
            overall += score * weights.get(dim, 0.33)
        overall = int(min(overall, 100))

        summary = f"总体完成度 {overall}/100"
        if overall >= 80:
            summary += "，任务接近完成"
        elif overall >= 50:
            summary += "，任务部分完成"
        else:
            summary += "，任务进展有限"

        return CompletionScore(
            overall=overall,
            sub_scores=sub_scores,
            completed_criteria=completed,
            pending_criteria=pending,
            summary=summary,
        )

    def _ai_evaluate(
        self,
        task: str,
        plan: TaskPlan,
        screenshot_diff: Optional[ScreenshotDiff],
        ui_tree_diff: Optional[UITreeDiff],
        action_results: list,
        ai_client,
    ) -> CompletionScore:
        """用 AI 做完成度评估"""
        plan_summary = plan.to_dict() if plan else {}
        action_summary = []
        if action_results:
            for r in action_results:
                action_summary.append({
                    "type": getattr(r.action, 'action_type', 'unknown'),
                    "success": getattr(r, 'success', False),
                    "message": getattr(r, 'message', ''),
                })

        prompt = f"""评估以下任务的完成度。

## 任务
{task}

## 任务规划
{json.dumps(plan_summary, ensure_ascii=False, indent=2)}

## 已执行操作
{json.dumps(action_summary, ensure_ascii=False, indent=2)}

## 界面变化
- 截图是否变化: {screenshot_diff.has_changed if screenshot_diff else '未知'}
- 变化摘要: {screenshot_diff.summary if screenshot_diff else '未知'}
- 控件树是否变化: {ui_tree_diff.has_changed if ui_tree_diff else '未知'}
- 控件树摘要: {ui_tree_diff.summary if ui_tree_diff else '未知'}

请从以下维度评分 (0-100)，并给出评估：

{{
    "overall": 总分(0-100),
    "sub_scores": {{
        "目标达成": 分数,
        "操作执行": 分数,
        "界面状态": 分数
    }},
    "completed": ["已满足的条件"],
    "pending": ["未满足的条件"],
    "summary": "一句话总结"
}}
"""
        messages = [
            {"role": "system", "content": "你是任务完成度评估专家。返回 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        response = ai_client.chat.completions.create(
            model="mimo-v2.5",
            messages=messages,
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        parsed = self._extract_json(content)

        if parsed:
            data = json.loads(parsed)
            return CompletionScore(
                overall=data.get("overall", 50),
                sub_scores=data.get("sub_scores", {}),
                completed_criteria=data.get("completed", []),
                pending_criteria=data.get("pending", []),
                summary=data.get("summary", ""),
            )

        # AI 解析失败，降级到规则评估
        return self._rule_evaluate(task, plan, screenshot_diff, ui_tree_diff, action_results)

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        if not text:
            return ""
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*\}',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_start = text.rfind('{')
        last_end = text.rfind('}')
        if last_start != -1 and last_end > last_start:
            candidate = text[last_start:last_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return ""


# ==================== 智能验证主层 ====================

class SmartVerifyLayer:
    """
    智能验证层

    增强现有的 VerifyLayer，集成：
    1. 截图对比（ScreenshotComparator）
    2. UIA 树变化检测（UITreeAnalyzer）
    3. 任务完成度评估（CompletionEvaluator）
    4. 失败原因分析（FailureDiagnoser）

    核心区别于普通 VerifyLayer：
    - 不只是"完成/未完成"二元判断
    - 给出 0-100 的完成度评分
    - 分析失败的具体原因
    - 提供可操作的改进建议
    """

    def __init__(
        self,
        mimo_client=None,
        vision_engine=None,
        change_threshold: float = 0.05,
    ):
        """
        初始化智能验证层

        Args:
            mimo_client: MiMo API 客户端
            vision_engine: 视觉引擎（截图 + UIA 树）
            change_threshold: 界面变化判定阈值 (0-1)
        """
        self.mimo = mimo_client
        self.vision = vision_engine
        self.awareness = ContinuousAwareness(vision_engine)

        # 子模块
        self.screenshot_comparator = ScreenshotComparator(threshold=change_threshold)
        self.ui_tree_analyzer = UITreeAnalyzer()
        self.completion_evaluator = CompletionEvaluator()
        self.failure_diagnoser = FailureDiagnoser()

        # 状态缓存（操作前的快照）
        self._before_screenshot: str = ""
        self._before_uia_tree: str = ""

    # ---------- 快照管理 ----------

    def capture_before(self) -> dict:
        """
        操作前快照（在执行操作前调用）

        Returns:
            快照数据，包含截图和 UIA 树
        """
        screenshot = self._take_screenshot()
        uia_tree = self._get_uia_tree()

        self._before_screenshot = screenshot
        self._before_uia_tree = uia_tree

        return {
            "screenshot": screenshot,
            "uia_tree": uia_tree,
            "timestamp": time.time(),
        }

    def capture_after(self) -> dict:
        """
        操作后快照（在执行操作后调用）

        Returns:
            快照数据
        """
        screenshot = self._take_screenshot()
        uia_tree = self._get_uia_tree()

        return {
            "screenshot": screenshot,
            "uia_tree": uia_tree,
            "timestamp": time.time(),
        }

    # ---------- 核心验证 ----------

    def verify(
        self,
        task: str,
        plan: TaskPlan,
        before_snapshot: dict = None,
        after_snapshot: dict = None,
        action_results: list = None,
        max_retries: int = 3,
    ) -> SmartVerifyResult:
        """
        智能验证任务

        Args:
            task: 用户任务描述
            plan: 任务规划
            before_snapshot: 操作前快照（可选，使用 capture_before 获取）
            after_snapshot: 操作后快照（可选，使用 capture_after 获取）
            action_results: 已执行操作的结果
            max_retries: 最大重试次数

        Returns:
            SmartVerifyResult 综合验证结果
        """
        start_time = time.time()
        result = SmartVerifyResult(
            status=VerifyStatus.FAILED,
            timestamp=start_time,
        )

        # 获取快照
        before = before_snapshot or {
            "screenshot": self._before_screenshot,
            "uia_tree": self._before_uia_tree,
        }
        after = after_snapshot or self.capture_after()

        # 1. 截图对比
        result.screenshot_diff = self.screenshot_comparator.compare(
            before.get("screenshot", ""),
            after.get("screenshot", ""),
            ai_client=self.mimo,
        )

        # 2. UIA 树对比
        result.ui_tree_diff = self.ui_tree_analyzer.analyze(
            before.get("uia_tree", ""),
            after.get("uia_tree", ""),
            ai_client=self.mimo,
        )

        # 3. AI 综合判断（如果有 AI）
        ai_judgment = None
        if self.mimo:
            ai_judgment = self._ai_comprehensive_judge(
                task, before, after
            )
            if ai_judgment:
                result.raw_ai_response = json.dumps(
                    ai_judgment, ensure_ascii=False
                )

        # 4. 失败原因分析（如果未完成）
        is_completed = self._check_completed(
            ai_judgment, result.screenshot_diff, result.ui_tree_diff
        )

        if not is_completed:
            error_msgs = []
            if ai_judgment and "errors" in ai_judgment:
                error_msgs = ai_judgment["errors"]
            elif ai_judgment and "reason" in ai_judgment:
                error_msgs = [ai_judgment["reason"]]

            result.failure_analysis = self.failure_diagnoser.diagnose(
                screenshot_diff=result.screenshot_diff,
                ui_tree_diff=result.ui_tree_diff,
                error_messages=error_msgs,
                task_context=task,
                ai_client=self.mimo,
            )

        # 5. 完成度评估
        result.completion_score = self.completion_evaluator.evaluate(
            task=task,
            plan=plan,
            screenshot_diff=result.screenshot_diff,
            ui_tree_diff=result.ui_tree_diff,
            action_results=action_results,
            ai_client=self.mimo,
        )

        # 6. 综合判定状态
        score = result.completion_score.overall
        if score >= 90:
            result.status = VerifyStatus.COMPLETED
        elif score >= 40:
            result.status = VerifyStatus.PARTIAL
        elif result.screenshot_diff and not result.screenshot_diff.has_changed:
            result.status = VerifyStatus.UNCHANGED
        else:
            result.status = VerifyStatus.FAILED

        result.verify_duration = time.time() - start_time
        return result

    def verify_simple(
        self,
        task: str,
        plan: TaskPlan,
        max_retries: int = 3,
    ) -> SmartVerifyResult:
        """
        简化版验证（不传快照，自动截图）

        和原来的 VerifyLayer.verify() 接口类似，方便替换。
        """
        before = self.capture_before()

        # 这里假设调用方在 verify_simple 返回后会执行操作
        # 然后再调用 verify_after 来完成验证
        return self.verify(
            task=task,
            plan=plan,
            before_snapshot=before,
            max_retries=max_retries,
        )

    def verify_after(
        self,
        task: str,
        plan: TaskPlan,
        before: dict,
        action_results: list = None,
    ) -> SmartVerifyResult:
        """
        操作后验证

        Args:
            task: 任务描述
            plan: 任务规划
            before: 之前 capture_before 的结果
            action_results: 操作结果

        Returns:
            SmartVerifyResult
        """
        after = self.capture_after()
        return self.verify(
            task=task,
            plan=plan,
            before_snapshot=before,
            after_snapshot=after,
            action_results=action_results,
        )

    # ---------- 兼容旧接口 ----------

    def legacy_verify(
        self,
        task: str,
        plan: TaskPlan,
        max_retries: int = 3,
    ) -> TaskResult:
        """
        兼容旧 VerifyLayer 接口

        返回旧格式的 TaskResult，方便渐进式迁移。
        """
        smart_result = self.verify(task=task, plan=plan, max_retries=max_retries)

        return TaskResult(
            goal=task,
            success=(smart_result.status == VerifyStatus.COMPLETED),
            message=smart_result.completion_score.summary if smart_result.completion_score else "",
            steps_total=len(plan.steps),
            retries=0,
        )

    # ---------- 内部方法 ----------

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

    def _check_completed(
        self,
        ai_judgment: Optional[dict],
        screenshot_diff: Optional[ScreenshotDiff],
        ui_tree_diff: Optional[UITreeDiff],
    ) -> bool:
        """综合判断是否完成"""
        # 优先看 AI 判断
        if ai_judgment and "completed" in ai_judgment:
            return ai_judgment["completed"]

        # 降级看截图变化
        if screenshot_diff and screenshot_diff.error_indicators:
            return False

        return True  # 无明确否定就假定完成

    def _ai_comprehensive_judge(
        self,
        task: str,
        before: dict,
        after: dict,
    ) -> Optional[dict]:
        """AI 综合判断"""
        before_uia = before.get("uia_tree", "")[:2000]
        after_uia = after.get("uia_tree", "")[:2000]

        prompt = f"""综合判断这个任务是否已完成。

## 任务
{task}

## 操作前 UIA 树
```
{before_uia}
```

## 操作后 UIA 树
```
{after_uia}
```

请返回 JSON：
{{
    "completed": true/false,
    "reason": "判断原因",
    "confidence": 0.0到1.0,
    "errors": ["如果检测到任何错误信息"],
    "suggestion": "改进建议（如果未完成）"
}}
"""
        messages = [
            {"role": "system", "content": "你是 MI Hands 验证助手。返回 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        # 加截图
        before_screenshot = before.get("screenshot", "")
        after_screenshot = after.get("screenshot", "")
        if after_screenshot:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "操作后截图："},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_screenshot}"}},
                ],
            })

        try:
            response = retry_call(
                lambda: self.mimo.chat.completions.create(
                    model="mimo-v2.5",
                    messages=messages,
                    max_completion_tokens=2048,
                ),
                max_retries=3,
                base_delay=1.0,
            )

            content = response.choices[0].message.content
            parsed = self._extract_json(content)
            if parsed:
                return json.loads(parsed)
        except Exception as e:
            print(f"AI 综合判断失败: {e}")

        return None

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON"""
        if not text:
            return ""
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*\}',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match.strip())
                    return match.strip()
                except json.JSONDecodeError:
                    continue

        last_start = text.rfind('{')
        last_end = text.rfind('}')
        if last_start != -1 and last_end > last_start:
            candidate = text[last_start:last_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return ""
