"""
AdvancedEngines - 高级执行引擎

支持更多软件架构的执行方案：
1. Qt Accessibility - Qt 应用控件访问
2. Image Recognition - 图像识别定位
3. Script Injection - 脚本注入执行
4. Java Accessibility - Java 应用控件访问
5. Flutter Accessibility - Flutter 应用控件访问
6. Selenium - 浏览器自动化

核心思想：让 MI Hands 能操作更多类型的软件
"""

import time
import sys
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum


# ============================================================
# 公共工具函数（避免重复代码）
# ============================================================

def find_in_tree(parent, name: str, depth: int = 0, max_depth: int = 10) -> Optional[Dict]:
    """
    在控件树中查找指定名称的控件（公共函数）

    Args:
        parent: 父控件
        name: 要查找的控件名称
        depth: 当前深度
        max_depth: 最大深度

    Returns:
        找到的控件信息，未找到返回 None
    """
    if depth > max_depth:
        return None

    try:
        # 检查当前控件
        if parent.Name and name.lower() in parent.Name.lower():
            rect = parent.BoundingRectangle
            if rect:
                return {
                    "name": parent.Name,
                    "control_type": parent.ControlTypeName,
                    "rect": (rect.left, rect.top, rect.right, rect.bottom),
                    "center": ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2),
                }

        # 递归查找子控件
        children = parent.GetChildren()
        for child in children:
            result = find_in_tree(child, name, depth + 1, max_depth)
            if result:
                return result

    except Exception:
        pass

    return None


class AdvancedEngineType(Enum):
    """高级引擎类型"""
    QT_ACCESSIBILITY = "qt_accessibility"  # Qt 控件访问
    IMAGE_RECOGNITION = "image_recognition"  # 图像识别
    SCRIPT_INJECTION = "script_injection"    # 脚本注入
    JAVA_ACCESSIBILITY = "java_accessibility"  # Java 控件访问
    FLUTTER_ACCESSIBILITY = "flutter_accessibility"  # Flutter 控件访问
    SELENIUM = "selenium"  # 浏览器自动化


class UIABasedEngine:
    """
    基于 UIA 的引擎基类

    提供通用的 find_element 和 click_element 实现
    子类只需覆写 _match_window 方法
    """

    def __init__(self):
        """初始化"""
        pass

    def is_available(self) -> bool:
        """检查是否可用"""
        try:
            import ctypes
            return hasattr(ctypes, 'windll')
        except (ImportError, Exception):
            return False

    def _match_window(self, window, app_name: str) -> bool:
        """
        匹配窗口（子类覆写）

        Args:
            window: UIA 窗口对象
            app_name: 应用名称

        Returns:
            是否匹配
        """
        window_name = window.Name or ""
        return app_name.lower() in window_name.lower()

    def find_element(self, name: str, app_name: str = "") -> Optional[Dict]:
        """
        查找控件

        Args:
            name: 控件名称
            app_name: 应用名称

        Returns:
            控件信息
        """
        try:
            import uiautomation as auto

            # 获取所有窗口
            root = auto.GetRootControl()
            windows = root.GetChildren()

            for window in windows:
                if self._match_window(window, app_name):
                    # 递归查找控件
                    element = find_in_tree(window, name)
                    if element:
                        return element

            return None

        except Exception as e:
            print(f"{self.__class__.__name__} error: {e}")
            return None

    def click_element(self, element: Dict) -> bool:
        """点击控件"""
        try:
            import pyautogui
            center = element.get("center", (0, 0))
            pyautogui.click(center[0], center[1])
            return True
        except Exception as e:
            print(f"{self.__class__.__name__} click error: {e}")
            return False

    def getCapabilities(self) -> List[str]:
        return ["find_element", "click_element"]


class QtAccessibilityEngine(UIABasedEngine):
    """
    Qt Accessibility 引擎

    通过 Qt 的 Accessibility API 访问控件
    支持：Krita、GIMP、Blender 等 Qt 应用
    """

    def _match_window(self, window, app_name: str) -> bool:
        """匹配 Qt 窗口"""
        window_name = window.Name or ""
        return app_name.lower() in window_name.lower()


class ImageRecognitionEngine:
    """
    图像识别引擎

    通过截图识别目标位置
    支持：任何软件
    """

    def __init__(self):
        """初始化图像识别引擎"""
        self._opencv_available = False
        self._check_opencv()

    def _check_opencv(self):
        """检查 OpenCV 是否可用"""
        try:
            import cv2
            self._opencv_available = True
        except ImportError:
            self._opencv_available = False

    def is_available(self) -> bool:
        """检查是否可用"""
        return self._opencv_available

    def find_template(self, template_path: str, screenshot_path: str, threshold: float = 0.8) -> Optional[Dict]:
        """
        模板匹配

        Args:
            template_path: 模板图片路径
            screenshot_path: 截图路径
            threshold: 匹配阈值

        Returns:
            匹配位置
        """
        if not self._opencv_available:
            return None

        try:
            import cv2
            import numpy as np

            # 读取图片
            screenshot = cv2.imread(screenshot_path)
            template = cv2.imread(template_path)

            if screenshot is None or template is None:
                return None

            # 模板匹配
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                h, w = template.shape[:2]
                x, y = max_loc
                return {
                    "x": x + w // 2,
                    "y": y + h // 2,
                    "confidence": max_val,
                    "rect": (x, y, x + w, y + h),
                }

            return None

        except Exception as e:
            print(f"Template matching error: {e}")
            return None

    def find_by_color(self, color: Tuple[int, int, int], screenshot_path: str, tolerance: int = 30) -> Optional[Dict]:
        """
        通过颜色查找位置

        Args:
            color: 目标颜色 (B, G, R)
            screenshot_path: 截图路径
            tolerance: 颜色容差

        Returns:
            匹配位置
        """
        if not self._opencv_available:
            return None

        try:
            import cv2
            import numpy as np

            # 读取图片
            screenshot = cv2.imread(screenshot_path)
            if screenshot is None:
                return None

            # 创建颜色掩码
            lower = np.array([max(0, c - tolerance) for c in color])
            upper = np.array([min(255, c + tolerance) for c in color])
            mask = cv2.inRange(screenshot, lower, upper)

            # 找到匹配区域
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # 找到最大的区域
                largest = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest)
                return {
                    "x": x + w // 2,
                    "y": y + h // 2,
                    "area": cv2.contourArea(largest),
                }

            return None

        except Exception as e:
            print(f"Color detection error: {e}")
            return None

    def take_screenshot(self, save_path: str = "screenshot.png") -> bool:
        """截图"""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            return True
        except Exception as e:
            print(f"Screenshot error: {e}")
            return False

    def getCapabilities(self) -> List[str]:
        return ["find_template", "find_by_color", "take_screenshot"]


class ScriptInjectionEngine:
    """
    脚本注入引擎

    直接调用应用的 API
    支持：Python 应用、COM 组件
    """

    def __init__(self):
        """初始化脚本注入引擎"""
        pass

    def is_available(self) -> bool:
        """检查是否可用"""
        return True

    def execute_python(self, code: str, timeout: int = 30) -> Dict:
        """
        执行 Python 代码（带安全检查）

        Args:
            code: Python 代码
            timeout: 超时时间

        Returns:
            执行结果
        """
        try:
            import subprocess
            import tempfile

            # 安全检查：使用 ScriptExecutor 的白名单机制
            from .script_executor import ScriptExecutor
            executor = ScriptExecutor()
            safety_result = executor._check_code_safety(code)
            if not safety_result["safe"]:
                return {
                    "success": False,
                    "output": "",
                    "error": f"安全检查失败: {safety_result['reason']}"
                }

            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name

            try:
                # 执行
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                }

            finally:
                import os
                os.unlink(temp_file)

        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "执行超时"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def call_com(self, app_name: str, method: str, params: Dict = None) -> Dict:
        """
        调用 COM 组件

        Args:
            app_name: 应用名称
            method: 方法名
            params: 参数

        Returns:
            调用结果
        """
        try:
            import win32com.client

            # 连接到 COM 对象
            app = win32com.client.Dispatch(app_name)

            # 调用方法
            if params:
                result = getattr(app, method)(**params)
            else:
                result = getattr(app, method)()

            return {"success": True, "result": result}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def getCapabilities(self) -> List[str]:
        return ["execute_python", "call_com"]


class JavaAccessibilityEngine(UIABasedEngine):
    """
    Java Accessibility 引擎

    通过 Java Accessibility API 访问控件
    支持：IntelliJ IDEA、Eclipse、NetBeans 等 Java 应用
    """

    def is_available(self) -> bool:
        """检查是否可用"""
        try:
            # 检查 Java 是否安装
            import subprocess
            result = subprocess.run(["java", "-version"], capture_output=True, text=True)
            return result.returncode == 0
        except (ImportError, Exception):
            return False

    def _match_window(self, window, app_name: str) -> bool:
        """匹配 Java 窗口"""
        window_name = window.Name or ""
        return app_name.lower() in window_name.lower() or "java" in window_name.lower()


class FlutterAccessibilityEngine(UIABasedEngine):
    """
    Flutter Accessibility 引擎

    通过 Flutter 的 Accessibility API 访问控件
    支持：Flutter 应用
    """

    def _match_window(self, window, app_name: str) -> bool:
        """匹配 Flutter 窗口"""
        window_name = window.Name or ""
        return app_name.lower() in window_name.lower()


class SeleniumEngine:
    """
    Selenium 引擎

    通过 WebDriver 控制浏览器
    支持：Chrome、Firefox、Edge 等浏览器
    """

    def __init__(self):
        """初始化 Selenium 引擎"""
        self._driver = None

    def is_available(self) -> bool:
        """检查是否可用"""
        try:
            from selenium import webdriver
            return True
        except ImportError:
            return False

    def start_browser(self, browser: str = "chrome") -> bool:
        """
        启动浏览器

        Args:
            browser: 浏览器类型（chrome/firefox/edge）

        Returns:
            是否成功
        """
        try:
            from selenium import webdriver

            if browser == "chrome":
                from selenium.webdriver.chrome.options import Options
                options = Options()
                options.add_argument("--start-maximized")
                self._driver = webdriver.Chrome(options=options)
            elif browser == "firefox":
                from selenium.webdriver.firefox.options import Options
                options = Options()
                self._driver = webdriver.Firefox(options=options)
            elif browser == "edge":
                from selenium.webdriver.edge.options import Options
                options = Options()
                self._driver = webdriver.Edge(options=options)

            return self._driver is not None

        except Exception as e:
            print(f"Browser start error: {e}")
            return False

    def navigate(self, url: str) -> bool:
        """导航到 URL"""
        if self._driver:
            try:
                self._driver.get(url)
                return True
            except Exception as e:
                print(f"Navigation error: {e}")
        return False

    def find_element(self, by: str, value: str) -> Optional[Dict]:
        """
        查找元素

        Args:
            by: 查找方式（id/xpath/css_selector/name/class_name）
            value: 查找值

        Returns:
            元素信息
        """
        if not self._driver:
            return None

        try:
            from selenium.webdriver.common.by import By

            by_map = {
                "id": By.ID,
                "xpath": By.XPATH,
                "css_selector": By.CSS_SELECTOR,
                "name": By.NAME,
                "class_name": By.CLASS_NAME,
            }

            element = self._driver.find_element(by_map.get(by, By.ID), value)
            location = element.location
            size = element.size

            return {
                "element": element,
                "x": location["x"] + size["width"] // 2,
                "y": location["y"] + size["height"] // 2,
                "width": size["width"],
                "height": size["height"],
            }

        except Exception as e:
            print(f"Element find error: {e}")
            return None

    def click_element(self, element: Dict) -> bool:
        """点击元素"""
        if "element" in element:
            try:
                element["element"].click()
                return True
            except Exception as e:
                print(f"Click error: {e}")
        return False

    def type_text(self, element: Dict, text: str) -> bool:
        """在元素中输入文字"""
        if "element" in element:
            try:
                element["element"].send_keys(text)
                return True
            except Exception as e:
                print(f"Type error: {e}")
        return False

    def get_page_source(self) -> str:
        """获取页面源码"""
        if self._driver:
            return self._driver.page_source
        return ""

    def quit(self):
        """关闭浏览器"""
        if self._driver:
            self._driver.quit()
            self._driver = None

    def getCapabilities(self) -> List[str]:
        return ["navigate", "find_element", "click_element", "type_text", "get_page_source"]


class AdvancedEngineManager:
    """
    高级引擎管理器

    管理所有高级执行引擎
    """

    def __init__(self):
        """初始化高级引擎管理器"""
        self.engines = {
            AdvancedEngineType.QT_ACCESSIBILITY: QtAccessibilityEngine(),
            AdvancedEngineType.IMAGE_RECOGNITION: ImageRecognitionEngine(),
            AdvancedEngineType.SCRIPT_INJECTION: ScriptInjectionEngine(),
            AdvancedEngineType.JAVA_ACCESSIBILITY: JavaAccessibilityEngine(),
            AdvancedEngineType.FLUTTER_ACCESSIBILITY: FlutterAccessibilityEngine(),
            AdvancedEngineType.SELENIUM: SeleniumEngine(),
        }

    def get_available_engines(self) -> List[AdvancedEngineType]:
        """获取所有可用的高级引擎"""
        available = []
        for engine_type, engine in self.engines.items():
            if engine.is_available():
                available.append(engine_type)
        return available

    def get_engine(self, engine_type: AdvancedEngineType):
        """获取指定引擎"""
        return self.engines.get(engine_type)

    def find_element(self, name: str, app_name: str = "") -> Optional[Dict]:
        """使用 Qt Accessibility 查找元素"""
        engine = self.engines.get(AdvancedEngineType.QT_ACCESSIBILITY)
        if engine and engine.is_available():
            return engine.find_element(name, app_name)
        return None

    def find_by_image(self, template_path: str, screenshot_path: str) -> Optional[Dict]:
        """使用图像识别查找位置"""
        engine = self.engines.get(AdvancedEngineType.IMAGE_RECOGNITION)
        if engine and engine.is_available():
            return engine.find_template(template_path, screenshot_path)
        return None

    def execute_script(self, code: str) -> Dict:
        """使用脚本注入执行代码"""
        engine = self.engines.get(AdvancedEngineType.SCRIPT_INJECTION)
        if engine and engine.is_available():
            return engine.execute_python(code)
        return {"success": False, "error": "Script injection not available"}
