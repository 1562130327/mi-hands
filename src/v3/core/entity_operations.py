"""
EntityOperations - 实体操作

借鉴 desktop-touch-mcp 和 UFO 的设计理念：
1. 用「实体」代替「坐标」
2. 基于控件语义操作
3. 支持属性定位（AutomationId/Name）— 借鉴 UFO
4. 提供操作置信度
5. 减少静默失败

核心思想：操作「确定按钮」而不是「坐标(300,400)」
关键优势：不管窗口怎么移动，都能找到控件
"""

import time
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class EntityType(Enum):
    """实体类型"""
    BUTTON = "button"
    TEXT_FIELD = "text_field"
    MENU_ITEM = "menu_item"
    LINK = "link"
    ICON = "icon"
    LIST_ITEM = "list_item"
    TAB = "tab"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SLIDER = "slider"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """
    UI 实体

    代表一个可操作的 UI 元素
    """
    entity_id: str              # 唯一标识
    name: str                   # 显示名称
    entity_type: EntityType     # 实体类型
    rect: Tuple[int, int, int, int]  # 位置 (x1, y1, x2, y2)
    center: Tuple[int, int]     # 中心点
    confidence: float           # 置信度 (0-1)
    context: Dict[str, Any]     # 额外上下文
    accessibility: Dict[str, Any]  # 辅助功能信息


class EntityResolver:
    """
    实体解析器

    支持多种定位方式（借鉴 UFO）：
    1. 名称定位 — FindByName
    2. AutomationId 定位 — FindByAutomationId
    3. 索引定位 — 按索引查找
    4. 类型定位 — 按控件类型查找
    5. 模糊匹配 — 名称包含关键字

    关键优势：不管窗口怎么移动，都能找到控件
    """

    def __init__(self, uia_engine=None):
        """
        初始化实体解析器

        Args:
            uia_engine: UIA 引擎（用于获取控件树）
        """
        self.uia_engine = uia_engine
        self.entity_cache: Dict[str, Entity] = {}

    # ============================================================
    # UFO 风格的属性定位（核心优势）
    # ============================================================

    def find_by_name(self, name: str, partial: bool = False) -> Optional[Entity]:
        """
        通过名称查找控件（UFO 风格）

        不管窗口怎么移动，名称不变，永远能找到

        Args:
            name: 控件名称
            partial: 是否模糊匹配（名称包含关键字）

        Returns:
            找到的控件
        """
        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree:
                for i, node in enumerate(tree.nodes):
                    node_name = node.name or ""
                    if partial:
                        if name in node_name:
                            entity = self._node_to_entity(node, i)
                            self.entity_cache[entity.entity_id] = entity
                            return entity
                    else:
                        if node_name == name:
                            entity = self._node_to_entity(node, i)
                            self.entity_cache[entity.entity_id] = entity
                            return entity

        return None

    def find_by_automation_id(self, automation_id: str) -> Optional[Entity]:
        """
        通过 AutomationId 查找控件（UFO 风格）

        AutomationId 是控件的固定标识，不管窗口怎么移动都不变

        Args:
            automation_id: 控件的 AutomationId

        Returns:
            找到的控件
        """
        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree:
                for i, node in enumerate(tree.nodes):
                    # 检查节点的 accessibility 信息
                    node_id = getattr(node, 'automation_id', None) or ""
                    if node_id == automation_id:
                        entity = self._node_to_entity(node, i)
                        self.entity_cache[entity.entity_id] = entity
                        return entity

        return None

    def find_by_control_type(self, control_type: str) -> List[Entity]:
        """
        通过控件类型查找所有控件

        Args:
            control_type: 控件类型（如 "Button", "Edit"）

        Returns:
            匹配的控件列表
        """
        results = []

        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree:
                for i, node in enumerate(tree.nodes):
                    node_type = getattr(node, 'control_type', '') or ""
                    if control_type.lower() in node_type.lower():
                        entity = self._node_to_entity(node, i)
                        results.append(entity)

        return results

    def find_by_fuzzy(self, keyword: str) -> List[Entity]:
        """
        模糊查找控件

        查找名称包含关键字的所有控件

        Args:
            keyword: 关键字

        Returns:
            匹配的控件列表
        """
        results = []

        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree:
                for i, node in enumerate(tree.nodes):
                    node_name = node.name or ""
                    if keyword.lower() in node_name.lower():
                        entity = self._node_to_entity(node, i)
                        results.append(entity)

        return results

    # ============================================================
    # 保留原有的定位方式
    # ============================================================

    def resolve_by_name(self, name: str, entity_type: EntityType = None) -> Optional[Entity]:
        """
        通过名称解析实体（兼容旧接口）

        Args:
            name: 实体名称
            entity_type: 期望的实体类型

        Returns:
            解析到的实体
        """
        entity = self.find_by_name(name)
        if entity and (entity_type is None or entity.entity_type == entity_type):
            return entity
        return None

    def resolve_by_index(self, index: int) -> Optional[Entity]:
        """
        通过索引解析实体

        Args:
            index: 控件索引

        Returns:
            解析到的实体
        """
        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree and index < len(tree.nodes):
                node = tree.nodes[index]
                entity = self._node_to_entity(node, index)
                self.entity_cache[entity.entity_id] = entity
                return entity

        return None

    def resolve_by_type(self, entity_type: EntityType) -> List[Entity]:
        """
        通过类型解析所有实体

        Args:
            entity_type: 实体类型

        Returns:
            匹配的实体列表
        """
        results = []

        if self.uia_engine:
            tree = self.uia_engine._last_tree
            if tree:
                for i, node in enumerate(tree.nodes):
                    node_type = self._classify_node(node)
                    if node_type == entity_type:
                        entity = self._node_to_entity(node, i)
                        results.append(entity)

        return results

    def _node_to_entity(self, node, index: int) -> Entity:
        """将 UIA 节点转换为实体"""
        entity_type = self._classify_node(node)

        rect = (0, 0, 0, 0)
        if node.rect:
            rect = tuple(node.rect)

        center = (
            (rect[0] + rect[2]) // 2,
            (rect[1] + rect[3]) // 2
        )

        return Entity(
            entity_id=f"entity_{index}",
            name=node.name or f"element_{index}",
            entity_type=entity_type,
            rect=rect,
            center=center,
            confidence=0.9,
            context={"index": index},
            accessibility={
                "control_type": node.control_type,
                "name": node.name,
                "automation_id": getattr(node, 'automation_id', None),
            }
        )

    def _classify_node(self, node) -> EntityType:
        """分类节点类型"""
        control_type = getattr(node, 'control_type', '') or ''

        if 'button' in control_type.lower():
            return EntityType.BUTTON
        elif 'edit' in control_type.lower() or 'text' in control_type.lower():
            return EntityType.TEXT_FIELD
        elif 'menu' in control_type.lower():
            return EntityType.MENU_ITEM
        elif 'link' in control_type.lower():
            return EntityType.LINK
        elif 'list' in control_type.lower():
            return EntityType.LIST_ITEM
        elif 'tab' in control_type.lower():
            return EntityType.TAB
        elif 'check' in control_type.lower():
            return EntityType.CHECKBOX
        elif 'radio' in control_type.lower():
            return EntityType.RADIO
        else:
            return EntityType.UNKNOWN


class EntityExecutor:
    """
    实体执行器

    执行基于实体的操作
    """

    def __init__(self, uia_engine=None):
        """
        初始化实体执行器

        Args:
            uia_engine: UIA 引擎
        """
        self.uia_engine = uia_engine

    def click_entity(self, entity: Entity) -> Dict[str, Any]:
        """
        点击实体

        Args:
            entity: 要点击的实体

        Returns:
            执行结果
        """
        try:
            import pyautogui

            # 点击实体中心
            pyautogui.click(entity.center[0], entity.center[1])

            return {
                "success": True,
                "message": f"Clicked '{entity.name}' at {entity.center}",
                "entity": entity.name,
                "confidence": entity.confidence
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to click '{entity.name}': {e}",
                "entity": entity.name,
                "confidence": entity.confidence
            }

    def type_in_entity(self, entity: Entity, text: str) -> Dict[str, Any]:
        """
        在实体中输入文字

        Args:
            entity: 目标实体
            text: 要输入的文字

        Returns:
            执行结果
        """
        try:
            import pyautogui

            # 点击实体获取焦点
            pyautogui.click(entity.center[0], entity.center[1])
            time.sleep(0.1)

            # 输入文字
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")

            return {
                "success": True,
                "message": f"Typed '{text}' in '{entity.name}'",
                "entity": entity.name,
                "confidence": entity.confidence
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to type in '{entity.name}': {e}",
                "entity": entity.name,
                "confidence": entity.confidence
            }

    def double_click_entity(self, entity: Entity) -> Dict[str, Any]:
        """
        双击实体

        Args:
            entity: 要双击的实体

        Returns:
            执行结果
        """
        try:
            import pyautogui
            import win32gui

            # 记住当前前台窗口
            original_window = win32gui.GetForegroundWindow()

            # 双击实体中心
            pyautogui.doubleClick(entity.center[0], entity.center[1])

            # 重新激活原窗口
            if original_window:
                time.sleep(0.1)
                win32gui.SetForegroundWindow(original_window)

            return {
                "success": True,
                "message": f"Double-clicked '{entity.name}' at {entity.center}",
                "entity": entity.name,
                "confidence": entity.confidence
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to double-click '{entity.name}': {e}",
                "entity": entity.name,
                "confidence": entity.confidence
            }
