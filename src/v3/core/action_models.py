"""
动作数据模型 - 定义执行动作的数据结构

参考 UFO 的 Action Schema 设计
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(Enum):
    """动作类型"""
    CLICK = "click"           # 点击控件
    DOUBLE_CLICK = "double_click"  # 双击控件
    TYPE_TEXT = "type_text"    # 输入文字
    PRESS_KEY = "press_key"   # 按键
    HOTKEY = "hotkey"          # 组合键
    SCROLL = "scroll"          # 滚动
    DRAG = "drag"              # 拖拽
    WAIT = "wait"              # 等待
    SCREENSHOT = "screenshot"  # 截图验证
    ANALYZE = "analyze"        # AI 分析
    # 新增：智能绘制方案
    DRAW_PATH = "draw_path"          # 手绘路径（pyautogui）
    DRAW_CURVE = "draw_curve"        # 贝塞尔曲线（pyautogui）
    DRAW_CIRCLE = "draw_circle"      # 圆形（pyautogui）
    DRAW_PRECISE = "draw_precise"    # 精细绘制（Win32 API，模拟压感）
    DRAW_BATCH = "draw_batch"        # 批量绘制（PIL 直接生成）


@dataclass
class Action:
    """
    单个执行动作

    参考 UFO 的 TargetInfo + Action 设计
    """
    action_type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""           # 描述（给人看）
    target_control: str = ""        # 目标控件名称
    target_index: int = -1          # 目标控件索引（UIA 树）
    fallback_action: Optional["Action"] = None  # 降级动作

    def to_dict(self) -> dict:
        """转成字典（方便序列化）"""
        return {
            "action_type": self.action_type.value,
            "params": self.params,
            "description": self.description,
            "target_control": self.target_control,
            "target_index": self.target_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        """从字典创建"""
        return cls(
            action_type=ActionType(data["action_type"]),
            params=data.get("params", {}),
            description=data.get("description", ""),
            target_control=data.get("target_control", ""),
            target_index=data.get("target_index", -1),
        )


@dataclass
class TaskPlan:
    """
    任务规划

    参考 UFO 的 AppAgentResponse 设计
    """
    goal: str                          # 用户目标
    steps: list[Action] = field(default_factory=list)  # 执行步骤
    requires_screenshot: bool = True   # 是否需要截图验证
    max_retries: int = 3               # 最大重试次数
    context: dict = field(default_factory=dict)  # 额外上下文

    def add_step(self, action: Action):
        """添加步骤"""
        self.steps.append(action)

    def to_dict(self) -> dict:
        """转成字典"""
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "requires_screenshot": self.requires_screenshot,
            "max_retries": self.max_retries,
        }


@dataclass
class ActionResult:
    """
    单个动作的执行结果
    """
    action: Action
    success: bool
    message: str = ""
    screenshot: str = ""  # 执行后的截图（base64）


@dataclass
class TaskResult:
    """
    整体任务的执行结果
    """
    goal: str
    success: bool
    message: str = ""
    steps_completed: int = 0
    steps_total: int = 0
    retries: int = 0
    action_results: list[ActionResult] = field(default_factory=list)
