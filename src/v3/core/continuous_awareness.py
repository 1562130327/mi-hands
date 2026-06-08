"""
ContinuousAwareness - 持续感知引擎

借鉴 cellar 的 Cortex 设计：
1. 持续监控界面变化
2. 检测操作的时效性
3. 发现意外副作用
4. 提供元素置信度评分

核心思想：不是"操作完再看"，而是"边操作边看"
"""

import time
import hashlib
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ElementState:
    """元素状态"""
    element_id: str           # 元素标识（控件名+路径）
    name: str                 # 显示名称
    rect: tuple               # 位置 (x1, y1, x2, y2)
    control_type: str         # 控件类型
    confidence: float         # 置信度 (0-1)
    last_seen: float          # 最后看到的时间戳
    hash: str = ""            # 状态哈希（用于变化检测）


@dataclass
class SideEffect:
    """副作用检测"""
    expected: str             # 预期结果
    actual: str               # 实际结果
    severity: str             # 严重程度: info/warning/error
    suggestion: str           # 建议


class ContinuousAwareness:
    """
    持续感知引擎

    借鉴 cellar 的 Cortex 设计：
    - freshness: 检测界面是否变化
    - side_effect: 检测操作是否产生意外结果
    - confidence: 每个元素的可信度评分

    核心思想：边操作边看，减少盲操作
    """

    def __init__(self, vision_engine=None):
        """
        初始化持续感知引擎

        Args:
            vision_engine: 视觉引擎（用于截图和 UIA 树）
        """
        self.vision = vision_engine
        self.element_cache: Dict[str, ElementState] = {}
        self.last_snapshot_hash: str = ""
        self.last_snapshot_time: float = 0
        self.side_effects: List[SideEffect] = []

    def take_snapshot(self) -> Dict[str, Any]:
        """
        获取当前界面快照

        Returns:
            快照数据：元素列表、哈希值、时间戳
        """
        if not self.vision:
            return {"elements": [], "hash": "", "timestamp": 0}

        try:
            # 获取 UIA 树
            tree_text = self.vision.get_snapshot()

            # 计算哈希
            current_hash = hashlib.md5(tree_text.encode()).hexdigest()

            # 解析元素（简化版）
            elements = self._parse_elements(tree_text)

            snapshot = {
                "elements": elements,
                "hash": current_hash,
                "timestamp": time.time(),
                "tree_text": tree_text
            }

            # 更新缓存
            self.last_snapshot_hash = current_hash
            self.last_snapshot_time = time.time()

            return snapshot

        except Exception as e:
            print(f"Snapshot failed: {e}")
            return {"elements": [], "hash": "", "timestamp": 0}

    def _parse_elements(self, tree_text: str) -> List[ElementState]:
        """
        解析 UIA 树文本为元素列表

        简化解析，提取关键元素
        """
        elements = []

        # 简单解析（实际应该用更复杂的解析器）
        lines = tree_text.split("\n")
        for i, line in enumerate(lines):
            if line.strip():
                # 提取元素信息
                element = ElementState(
                    element_id=f"elem_{i}",
                    name=line.strip()[:50],
                    rect=(0, 0, 0, 0),  # 简化
                    control_type="unknown",
                    confidence=0.8,
                    last_seen=time.time(),
                    hash=hashlib.md5(line.encode()).hexdigest()
                )
                elements.append(element)

        return elements

    def detect_changes(self, previous_hash: str = None) -> Dict[str, Any]:
        """
        检测界面变化

        Args:
            previous_hash: 之前的快照哈希

        Returns:
            变化检测结果
        """
        if not previous_hash:
            previous_hash = self.last_snapshot_hash

        current_snapshot = self.take_snapshot()
        current_hash = current_snapshot.get("hash", "")

        changed = current_hash != previous_hash

        return {
            "changed": changed,
            "current_hash": current_hash,
            "previous_hash": previous_hash,
            "timestamp": current_snapshot.get("timestamp", 0)
        }

    def detect_side_effects(self, expected: str, actual: str) -> SideEffect:
        """
        检测操作的副作用

        Args:
            expected: 预期结果
            actual: 实际结果

        Returns:
            副作用检测结果
        """
        # 简单的副作用检测
        if expected == actual:
            severity = "info"
            suggestion = "操作符合预期"
        elif "error" in actual.lower():
            severity = "error"
            suggestion = f"检测到错误: {actual}"
        else:
            severity = "warning"
            suggestion = f"预期 '{expected}'，实际 '{actual}'"

        side_effect = SideEffect(
            expected=expected,
            actual=actual,
            severity=severity,
            suggestion=suggestion
        )

        self.side_effects.append(side_effect)
        return side_effect

    def get_element_confidence(self, element_id: str) -> float:
        """
        获取元素的置信度

        Args:
            element_id: 元素标识

        Returns:
            置信度 (0-1)
        """
        element = self.element_cache.get(element_id)
        if element:
            return element.confidence
        return 0.0

    def update_element_confidence(self, element_id: str, confidence: float):
        """
        更新元素的置信度

        Args:
            element_id: 元素标识
            confidence: 新的置信度
        """
        if element_id in self.element_cache:
            self.element_cache[element_id].confidence = confidence

    def get_recent_side_effects(self, limit: int = 10) -> List[SideEffect]:
        """获取最近的副作用"""
        return self.side_effects[-limit:]

    def clear_side_effects(self):
        """清空副作用记录"""
        self.side_effects.clear()

    def is_fresh(self, max_age: float = 5.0) -> bool:
        """
        检查快照是否新鲜

        Args:
            max_age: 最大年龄（秒）

        Returns:
            是否新鲜
        """
        if self.last_snapshot_time == 0:
            return False
        return (time.time() - self.last_snapshot_time) < max_age
