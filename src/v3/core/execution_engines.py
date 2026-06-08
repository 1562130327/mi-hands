"""
ExecutionEngines - 万能执行引擎

支持多种执行方案，智能选择最优解：
1. pyautogui — 通用方案
2. Win32 API — 底层控制
3. UIA API — 控件操作
4. pywinauto — 兼容方案
5. PIL — 批量生成
6. 剪贴板 — 文字输入
7. CDP — 浏览器自动化
8. 物理 HID — 终极方案

核心思想：根据任务特点，自动选择最优执行方式
"""

import time
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod


class EngineType(Enum):
    """执行引擎类型"""
    PYAUTOGUI = "pyautogui"        # 通用方案
    WIN32_API = "win32api"          # 底层控制
    UIA = "uia"                    # 控件操作
    PYWINAUTO = "pywinauto"        # 兼容方案
    PIL = "pil"                    # 批量生成
    CLIPBOARD = "clipboard"        # 剪贴板
    CDP = "cdp"                    # 浏览器自动化
    PHYSICAL_HID = "physical_hid"  # 物理 HID
    MOCK = "mock"                  # 模拟模式


class TaskCategory(Enum):
    """任务类别"""
    CLICK = "click"              # 点击操作
    TYPE = "type"                # 输入操作
    DRAW = "draw"                # 绘制操作
    BROWSE = "browse"            # 浏览器操作
    FILE = "file"                # 文件操作
    SYSTEM = "system"            # 系统操作
    UNKNOWN = "unknown"          # 未知操作


@dataclass
class EngineResult:
    """引擎执行结果"""
    success: bool
    message: str
    engine: EngineType
    duration: float = 0
    data: dict = None


class BaseEngine(ABC):
    """基础执行引擎"""

    @abstractmethod
    def execute(self, action: str, params: dict) -> EngineResult:
        """执行操作"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        pass

    @abstractmethod
    def getCapabilities(self) -> List[str]:
        """获取引擎支持的操作"""
        pass


class PyAutoGUIEngine(BaseEngine):
    """pyautogui 执行引擎"""

    def is_available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    def getCapabilities(self) -> List[str]:
        return ["click", "double_click", "type", "hotkey", "scroll", "drag", "move"]

    def execute(self, action: str, params: dict) -> EngineResult:
        try:
            import pyautogui

            start_time = time.time()

            if action == "click":
                pyautogui.click(params["x"], params["y"])
            elif action == "double_click":
                pyautogui.doubleClick(params["x"], params["y"])
            elif action == "type":
                pyautogui.typewrite(params["text"], interval=0.02)
            elif action == "hotkey":
                pyautogui.hotkey(*params["keys"])
            elif action == "scroll":
                pyautogui.scroll(params["delta"], params["x"], params["y"])
            elif action == "move":
                pyautogui.moveTo(params["x"], params["y"])

            duration = time.time() - start_time
            return EngineResult(
                success=True,
                message=f"pyautogui: {action} completed",
                engine=EngineType.PYAUTOGUI,
                duration=duration
            )
        except Exception as e:
            return EngineResult(
                success=False,
                message=f"pyautogui error: {e}",
                engine=EngineType.PYAUTOGUI
            )


class Win32Engine(BaseEngine):
    """Win32 API 执行引擎"""

    def execute(self, action: str, params: dict) -> EngineResult:
        try:
            import ctypes
            user32 = ctypes.windll.user32

            start_time = time.time()

            if action == "click":
                x, y = params["x"], params["y"]
                user32.SetCursorPos(x, y)
                time.sleep(0.01)
                user32.mouse_event(0x0002, 0, 0, 0, 0)  # 左键按下
                time.sleep(0.01)
                user32.mouse_event(0x0004, 0, 0, 0, 0)  # 左键抬起
            elif action == "move":
                user32.SetCursorPos(params["x"], params["y"])

            duration = time.time() - start_time
            return EngineResult(
                success=True,
                message=f"Win32: {action} completed",
                engine=EngineType.WIN32_API,
                duration=duration
            )
        except Exception as e:
            return EngineResult(
                success=False,
                message=f"Win32 error: {e}",
                engine=EngineType.WIN32_API
            )

    def is_available(self) -> bool:
        try:
            import ctypes
            return hasattr(ctypes, 'windll')
        except (ImportError, Exception):
            return False

    def getCapabilities(self) -> List[str]:
        return ["click", "move", "type", "hotkey"]


class UIAEngine(BaseEngine):
    """UIA 执行引擎"""

    def execute(self, action: str, params: dict) -> EngineResult:
        try:
            from src.uia_engine import UIAEngine as UiaEngine

            engine = UiaEngine()
            index = params.get("index", -1)

            if action == "click" and index >= 0:
                result = engine.click_node(index)
                return EngineResult(
                    success="成功" in result or "已点击" in result,
                    message=result,
                    engine=EngineType.UIA
                )

            return EngineResult(
                success=False,
                message=f"UIA: unsupported action {action}",
                engine=EngineType.UIA
            )
        except Exception as e:
            return EngineResult(
                success=False,
                message=f"UIA error: {e}",
                engine=EngineType.UIA
            )

    def is_available(self) -> bool:
        try:
            from src.uia_engine import UIAEngine
            return True
        except ImportError:
            return False

    def getCapabilities(self) -> List[str]:
        return ["click", "double_click", "type"]


class PILDrawEngine(BaseEngine):
    """PIL 批量绘制引擎"""

    def execute(self, action: str, params: dict) -> EngineResult:
        try:
            from PIL import Image, ImageDraw

            start_time = time.time()

            width = params.get("width", 800)
            height = params.get("height", 600)
            elements = params.get("elements", [])
            output_path = params.get("output", "output.png")

            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)

            for elem in elements:
                elem_type = elem.get("type", "")
                if elem_type == "line":
                    x1, y1 = elem.get("start", [0, 0])
                    x2, y2 = elem.get("end", [0, 0])
                    color = elem.get("color", "black")
                    draw.line([(x1, y1), (x2, y2)], fill=color)
                elif elem_type == "ellipse":
                    cx, cy = elem.get("center", [0, 0])
                    rx, ry = elem.get("radius", [50, 50])
                    color = elem.get("color", "black")
                    draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], outline=color)

            img.save(output_path)

            duration = time.time() - start_time
            return EngineResult(
                success=True,
                message=f"PIL: saved to {output_path}",
                engine=EngineType.PIL,
                duration=duration
            )
        except Exception as e:
            return EngineResult(
                success=False,
                message=f"PIL error: {e}",
                engine=EngineType.PIL
            )

    def is_available(self) -> bool:
        try:
            from PIL import Image
            return True
        except ImportError:
            return False

    def getCapabilities(self) -> List[str]:
        return ["draw_batch", "draw_line", "draw_ellipse"]


class ClipboardEngine(BaseEngine):
    """剪贴板执行引擎"""

    def execute(self, action: str, params: dict) -> EngineResult:
        try:
            import pyperclip
            import pyautogui

            start_time = time.time()

            if action == "paste":
                text = params.get("text", "")
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")

            duration = time.time() - start_time
            return EngineResult(
                success=True,
                message=f"Clipboard: {action} completed",
                engine=EngineType.CLIPBOARD,
                duration=duration
            )
        except Exception as e:
            return EngineResult(
                success=False,
                message=f"Clipboard error: {e}",
                engine=EngineType.CLIPBOARD
            )

    def is_available(self) -> bool:
        try:
            import pyperclip
            return True
        except ImportError:
            return False

    def getCapabilities(self) -> List[str]:
        return ["paste"]


class EngineManager:
    """
    执行引擎管理器

    智能选择最优执行方式：
    1. 根据任务类别选择
    2. 根据可用引擎选择
    3. 根据历史成功率选择
    4. 支持降级链
    """

    def __init__(self):
        """初始化引擎管理器"""
        self.engines: Dict[EngineType, BaseEngine] = {}
        self.engine_stats: Dict[EngineType, Dict] = {}
        self.fallback_chains: Dict[TaskCategory, List[EngineType]] = {}

        # 注册引擎
        self._register_engines()

        # 初始化统计
        self._init_stats()

        # 初始化降级链
        self._init_fallback_chains()

    def _register_engines(self):
        """注册所有可用引擎"""
        engines = [
            PyAutoGUIEngine(),
            Win32Engine(),
            UIAEngine(),
            PILDrawEngine(),
            ClipboardEngine(),
        ]

        for engine in engines:
            if engine.is_available():
                # 根据引擎类型确定 EngineType
                if isinstance(engine, PyAutoGUIEngine):
                    self.engines[EngineType.PYAUTOGUI] = engine
                elif isinstance(engine, Win32Engine):
                    self.engines[EngineType.WIN32_API] = engine
                elif isinstance(engine, UIAEngine):
                    self.engines[EngineType.UIA] = engine
                elif isinstance(engine, PILDrawEngine):
                    self.engines[EngineType.PIL] = engine
                elif isinstance(engine, ClipboardEngine):
                    self.engines[EngineType.CLIPBOARD] = engine

    def _init_stats(self):
        """初始化统计"""
        for engine_type in EngineType:
            self.engine_stats[engine_type] = {
                "total": 0,
                "success": 0,
                "failure": 0,
                "avg_duration": 0
            }

    def _init_fallback_chains(self):
        """初始化降级链"""
        # 点击操作降级链
        self.fallback_chains[TaskCategory.CLICK] = [
            EngineType.UIA,           # 优先 UIA
            EngineType.PYAUTOGUI,     # 降级到 pyautogui
            EngineType.WIN32_API,     # 降级到 Win32
        ]

        # 输入操作降级链
        self.fallback_chains[TaskCategory.TYPE] = [
            EngineType.UIA,           # 优先 UIA
            EngineType.CLIPBOARD,     # 降级到剪贴板
            EngineType.PYAUTOGUI,     # 降级到 pyautogui
        ]

        # 绘制操作降级链
        self.fallback_chains[TaskCategory.DRAW] = [
            EngineType.PYAUTOGUI,     # 优先 pyautogui
            EngineType.WIN32_API,     # 降级到 Win32
            EngineType.PIL,           # 降级到 PIL
        ]

        # 浏览器操作降级链
        self.fallback_chains[TaskCategory.BROWSE] = [
            EngineType.CDP,           # 优先 CDP
            EngineType.PYAUTOGUI,     # 降级到 pyautogui
        ]

    def select_engine(self, task_category: TaskCategory) -> Optional[EngineType]:
        """
        智能选择最优引擎

        根据任务类别和历史成功率选择
        """
        # 获取降级链
        chain = self.fallback_chains.get(task_category, [
            EngineType.PYAUTOGUI,
            EngineType.WIN32_API,
        ])

        # 选择可用且成功率最高的引擎
        best_engine = None
        best_score = -1

        for engine_type in chain:
            if engine_type in self.engines:
                stats = self.engine_stats[engine_type]
                total = stats["total"]
                success = stats["success"]

                # 计算分数（考虑成功率和使用次数）
                if total == 0:
                    score = 0.5  # 未使用过的引擎给基础分
                else:
                    score = success / total

                # 优先选择成功率高的
                if score > best_score:
                    best_score = score
                    best_engine = engine_type

        return best_engine

    def execute(self, action: str, params: dict, task_category: TaskCategory = None) -> EngineResult:
        """
        执行操作（自动选择引擎）

        Args:
            action: 操作类型
            params: 操作参数
            task_category: 任务类别（可选）

        Returns:
            执行结果
        """
        # 确定任务类别
        if task_category is None:
            task_category = self._categorize_action(action)

        # 选择引擎
        engine_type = self.select_engine(task_category)

        if engine_type is None:
            return EngineResult(
                success=False,
                message="No available engine",
                engine=EngineType.MOCK
            )

        # 执行
        engine = self.engines[engine_type]
        result = engine.execute(action, params)

        # 更新统计
        self._update_stats(engine_type, result.success, result.duration)

        return result

    def execute_with_fallback(self, action: str, params: dict, task_category: TaskCategory = None) -> EngineResult:
        """
        执行操作（带降级链）

        如果主引擎失败，自动尝试下一个引擎
        """
        if task_category is None:
            task_category = self._categorize_action(action)

        chain = self.fallback_chains.get(task_category, [
            EngineType.PYAUTOGUI,
            EngineType.WIN32_API,
        ])

        for engine_type in chain:
            if engine_type in self.engines:
                engine = self.engines[engine_type]
                result = engine.execute(action, params)

                # 更新统计
                self._update_stats(engine_type, result.success, result.duration)

                if result.success:
                    return result

        return EngineResult(
            success=False,
            message="All engines failed",
            engine=EngineType.MOCK
        )

    def _categorize_action(self, action: str) -> TaskCategory:
        """根据操作类型推断任务类别"""
        click_actions = ["click", "double_click"]
        type_actions = ["type", "paste"]
        draw_actions = ["draw_path", "draw_curve", "draw_circle", "draw_batch"]
        browse_actions = ["navigate", "scroll_page"]

        if action in click_actions:
            return TaskCategory.CLICK
        elif action in type_actions:
            return TaskCategory.TYPE
        elif action in draw_actions:
            return TaskCategory.DRAW
        elif action in browse_actions:
            return TaskCategory.BROWSE
        else:
            return TaskCategory.UNKNOWN

    def _update_stats(self, engine_type: EngineType, success: bool, duration: float):
        """更新引擎统计"""
        stats = self.engine_stats[engine_type]
        stats["total"] += 1
        if success:
            stats["success"] += 1
        else:
            stats["failure"] += 1

        # 更新平均耗时
        total = stats["total"]
        old_avg = stats["avg_duration"]
        stats["avg_duration"] = (old_avg * (total - 1) + duration) / total

        # 学习优化：如果成功率低于 50%，从降级链中移除
        if total > 10:
            success_rate = stats["success"] / total
            if success_rate < 0.5:
                self._remove_from_fallback_chains(engine_type)

    def _remove_from_fallback_chains(self, engine_type: EngineType):
        """从降级链中移除低成功率的引擎"""
        for category, chain in self.fallback_chains.items():
            if engine_type in chain:
                chain.remove(engine_type)
                print(f"Removed {engine_type.value} from {category.value} fallback chain (low success rate)")

    def get_stats(self) -> Dict:
        """获取所有引擎统计"""
        return {
            engine_type.value: stats
            for engine_type, stats in self.engine_stats.items()
            if stats["total"] > 0
        }

    def get_available_engines(self) -> List[str]:
        """获取所有可用引擎"""
        return [engine_type.value for engine_type in self.engines.keys()]
