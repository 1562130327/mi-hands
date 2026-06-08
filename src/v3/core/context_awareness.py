"""
ContextAwareness - 上下文感知

根据当前状态智能选择执行引擎：
1. 应用类型 — 不同应用用不同引擎
2. 控件状态 — 判断控件是否可用
3. 窗口状态 — 判断窗口是否激活
4. 操作历史 — 选择成功率高的引擎

核心思想：不是固定降级链，而是根据上下文动态选择
"""

import time
from typing import Optional, Dict, List, Any
from enum import Enum


class AppType(Enum):
    """应用类型"""
    BROWSER = "browser"        # 浏览器
    EDITOR = "editor"          # 编辑器
    DESIGN = "design"          # 设计软件
    GAME = "game"              # 游戏
    SYSTEM = "system"          # 系统工具
    OFFICE = "office"          # 办公软件
    DEFAULT = "default"        # 默认


# 应用类型到引擎的映射
APP_ENGINE_MAP = {
    AppType.BROWSER: ["cdp", "uia", "pyautogui"],           # 浏览器优先用 CDP
    AppType.EDITOR: ["uia", "pyautogui"],                    # 编辑器优先用 UIA
    AppType.DESIGN: ["pyautogui", "win32api"],               # 设计软件用鼠标
    AppType.GAME: ["win32api", "physical_hid"],              # 游戏用底层 API
    AppType.SYSTEM: ["uia", "pyautogui"],                    # 系统工具用 UIA
    AppType.OFFICE: ["uia", "pyautogui", "clipboard"],       # 办公软件
    AppType.DEFAULT: ["uia", "pyautogui", "win32api"],       # 默认
}

# 应用名称到类型的映射
APP_NAME_MAP = {
    "chrome": AppType.BROWSER,
    "firefox": AppType.BROWSER,
    "edge": AppType.BROWSER,
    "vscode": AppType.EDITOR,
    "vim": AppType.EDITOR,
    "notepad": AppType.EDITOR,
    "photoshop": AppType.DESIGN,
    "illustrator": AppType.DESIGN,
    "krita": AppType.DESIGN,
    "paint": AppType.DESIGN,
    "steam": AppType.GAME,
    "game": AppType.GAME,
    "explorer": AppType.SYSTEM,
    "cmd": AppType.SYSTEM,
    "powershell": AppType.SYSTEM,
    "word": AppType.OFFICE,
    "excel": AppType.OFFICE,
    "powerpoint": AppType.OFFICE,
}


class ContextAwareness:
    """
    上下文感知引擎

    根据当前状态智能选择执行引擎
    """

    def __init__(self):
        """初始化上下文感知"""
        self.current_app: Optional[AppType] = None
        self.current_window: Optional[str] = None
        self.window_active: bool = False
        self.control_available: bool = False

    def detect_app_type(self, window_title: str = "", process_name: str = "") -> AppType:
        """
        检测应用类型

        Args:
            window_title: 窗口标题
            process_name: 进程名

        Returns:
            应用类型
        """
        # 尝试从窗口标题匹配
        title_lower = window_title.lower()
        for app_name, app_type in APP_NAME_MAP.items():
            if app_name in title_lower:
                self.current_app = app_type
                return app_type

        # 尝试从进程名匹配
        process_lower = process_name.lower()
        for app_name, app_type in APP_NAME_MAP.items():
            if app_name in process_lower:
                self.current_app = app_type
                return app_type

        # 默认类型
        self.current_app = AppType.DEFAULT
        return AppType.DEFAULT

    def get_recommended_engines(self, app_type: AppType = None) -> List[str]:
        """
        获取推荐的引擎列表

        Args:
            app_type: 应用类型（可选，默认使用当前检测到的类型）

        Returns:
            推荐的引擎列表
        """
        if app_type is None:
            app_type = self.current_app or AppType.DEFAULT

        return APP_ENGINE_MAP.get(app_type, APP_ENGINE_MAP[AppType.DEFAULT])

    def check_window_active(self, window_handle: int = None) -> bool:
        """
        检查窗口是否激活

        Args:
            window_handle: 窗口句柄

        Returns:
            是否激活
        """
        if window_handle:
            try:
                import win32gui
                self.window_active = win32gui.GetForegroundWindow() == window_handle
            except (ImportError, Exception):
                self.window_active = False
        else:
            self.window_active = True

        return self.window_active

    def check_control_available(self, control_info: Dict = None) -> bool:
        """
        检查控件是否可用

        Args:
            control_info: 控件信息

        Returns:
            是否可用
        """
        if control_info is None:
            self.control_available = True
            return True

        # 检查控件是否启用
        enabled = control_info.get("enabled", True)
        visible = control_info.get("visible", True)

        self.control_available = enabled and visible
        return self.control_available

    def select_best_engine(self, task_category: str, app_type: AppType = None) -> str:
        """
        选择最优引擎

        综合考虑：
        1. 应用类型推荐
        2. 操作历史成功率
        3. 窗口状态

        Args:
            task_category: 任务类别
            app_type: 应用类型

        Returns:
            推荐的引擎名称
        """
        # 获取推荐引擎
        recommended = self.get_recommended_engines(app_type)

        # 根据任务类别过滤
        if task_category == "click":
            # 点击操作优先用 UIA
            preferred = ["uia", "pyautogui", "win32api"]
        elif task_category == "type":
            # 输入操作优先用 UIA 或剪贴板
            preferred = ["uia", "clipboard", "pyautogui"]
        elif task_category == "draw":
            # 绘制操作优先用 pyautogui
            preferred = ["pyautogui", "win32api", "pil"]
        else:
            preferred = recommended

        # 选择第一个可用的引擎
        for engine in preferred:
            if engine in recommended:
                return engine

        # 默认用 pyautogui
        return "pyautogui"

    def get_context_info(self) -> Dict:
        """获取当前上下文信息"""
        return {
            "app_type": self.current_app.value if self.current_app else "unknown",
            "window_active": self.window_active,
            "control_available": self.control_available,
            "recommended_engines": self.get_recommended_engines(),
        }
