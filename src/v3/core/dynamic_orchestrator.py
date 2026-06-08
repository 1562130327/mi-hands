"""
DynamicOrchestrator - 动态引擎编排器

核心思想：不是固定降级链，而是动态分析任务，智能选择引擎组合

功能：
1. 分析任务，识别软件架构
2. 识别 UI 区域，选择最优引擎
3. 并行执行独立动作
4. 实时监控，动态调整
"""

import time
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


class ArchitectureType(Enum):
    """架构类型"""
    WIN32 = "win32"
    QT = "qt"
    ELECTRON = "electron"
    WPF = "wpf"
    JAVA = "java"
    FLUTTER = "flutter"
    WEBVIEW = "webview"
    UNKNOWN = "unknown"


@dataclass
class ExecutionPlan:
    """执行计划"""
    engines: List[str]          # 可用引擎
    primary: str                # 主引擎
    fallback: List[str]         # 降级方案
    mix_mode: bool              # 是否混合使用
    parallel: bool              # 是否并行执行
    estimated_time: float       # 预估耗时


class DynamicEngineOrchestrator:
    """
    动态引擎编排器

    核心思想：动态分析任务，智能选择引擎组合
    """

    def __init__(self):
        """初始化动态引擎编排器"""
        self.architecture_cache: Dict[str, ArchitectureType] = {}
        self.engine_stats: Dict[str, Dict] = {}

    def analyze_task(self, task: str, context: Dict = None) -> ExecutionPlan:
        """
        分析任务，生成执行计划

        Args:
            task: 任务描述
            context: 上下文信息（应用类型、窗口状态等）

        Returns:
            执行计划
        """
        context = context or {}

        # 1. 识别软件架构
        app_type = context.get("app_type", "default")
        architecture = self._detect_architecture(app_type)

        # 2. 选择引擎
        engines = self._select_engines(architecture, task)

        # 3. 判断是否混合使用
        mix_mode = self._should_mix(engines, task)

        # 4. 判断是否并行
        parallel = self._should_parallel(task)

        # 5. 预估耗时
        estimated_time = self._estimate_time(engines, task)

        return ExecutionPlan(
            engines=engines,
            primary=engines[0] if engines else "pyautogui",
            fallback=engines[1:] if len(engines) > 1 else [],
            mix_mode=mix_mode,
            parallel=parallel,
            estimated_time=estimated_time,
        )

    def _detect_architecture(self, app_type: str) -> ArchitectureType:
        """检测软件架构"""
        architecture_map = {
            "browser": ArchitectureType.WEBVIEW,
            "electron": ArchitectureType.ELECTRON,
            "qt": ArchitectureType.QT,
            "java": ArchitectureType.JAVA,
            "flutter": ArchitectureType.FLUTTER,
            "wpf": ArchitectureType.WPF,
            "default": ArchitectureType.WIN32,
        }
        return architecture_map.get(app_type, ArchitectureType.UNKNOWN)

    def _select_engines(self, architecture: ArchitectureType, task: str) -> List[str]:
        """根据架构选择引擎"""
        engine_map = {
            ArchitectureType.WIN32: ["uia", "pyautogui", "win32api"],
            ArchitectureType.QT: ["qt_accessibility", "pyautogui", "image_recognition"],
            ArchitectureType.ELECTRON: ["cdp", "selenium", "uia"],
            ArchitectureType.WPF: ["uia", "pyautogui"],
            ArchitectureType.JAVA: ["java_accessibility", "pyautogui"],
            ArchitectureType.FLUTTER: ["flutter_accessibility", "pyautogui"],
            ArchitectureType.WEBVIEW: ["cdp", "selenium", "pyautogui"],
            ArchitectureType.UNKNOWN: ["pyautogui", "uia", "win32api"],
        }

        engines = engine_map.get(architecture, ["pyautogui"])

        # 根据任务类型调整
        if "draw" in task.lower():
            engines = ["pyautogui", "win32api", "pil"] + engines
        elif "type" in task.lower():
            engines = ["uia", "clipboard", "pyautogui"] + engines

        return engines

    def _should_mix(self, engines: List[str], task: str) -> bool:
        """判断是否混合使用"""
        return len(engines) > 2 and ("complex" in task.lower() or "multi" in task.lower())

    def _should_parallel(self, task: str) -> bool:
        """判断是否并行执行"""
        return "batch" in task.lower() or "parallel" in task.lower()

    def _estimate_time(self, engines: List[str], task: str) -> float:
        """预估耗时"""
        base_time = 0.5
        if len(engines) > 3:
            base_time *= 1.5
        if "complex" in task.lower():
            base_time *= 2
        return base_time

    def execute_plan(self, plan: ExecutionPlan, actions: List[Dict]) -> List[Dict]:
        """执行计划"""
        if plan.parallel:
            return self._execute_parallel(plan, actions)
        else:
            return self._execute_serial(plan, actions)

    def _execute_serial(self, plan: ExecutionPlan, actions: List[Dict]) -> List[Dict]:
        """串行执行"""
        results = []
        for action in actions:
            result = self._execute_action(plan, action)
            results.append(result)
            if not result.get("success"):
                for fallback_engine in plan.fallback:
                    result = self._execute_with_engine(fallback_engine, action)
                    if result.get("success"):
                        break
        return results

    def _execute_parallel(self, plan: ExecutionPlan, actions: List[Dict]) -> List[Dict]:
        """并行执行"""
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._execute_action, plan, action) for action in actions]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def _execute_action(self, plan: ExecutionPlan, action: Dict) -> Dict:
        """执行单个动作"""
        return self._execute_with_engine(plan.primary, action)

    def _execute_with_engine(self, engine: str, action: Dict) -> Dict:
        """使用指定引擎执行动作"""
        try:
            action_type = action.get("type", "")
            params = action.get("params", {})

            if engine == "pyautogui":
                return self._execute_pyautogui(action_type, params)
            elif engine == "uia":
                return self._execute_uia(action_type, params)
            elif engine == "win32api":
                return self._execute_win32(action_type, params)
            elif engine == "qt_accessibility":
                return self._execute_qt(action_type, params)
            elif engine == "selenium":
                return self._execute_selenium(action_type, params)
            else:
                return {"success": False, "error": f"未知引擎: {engine}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_uia(self, action_type: str, params: Dict) -> Dict:
        """使用 UIA 引擎执行"""
        try:
            from ..uia_engine import UIAEngine
            engine = UIAEngine()

            if action_type == "click":
                index = params.get("index", -1)
                if index >= 0:
                    result = engine.click_node(index)
                    return {"success": "成功" in result or "已点击" in result, "message": result}
            elif action_type == "type":
                text = params.get("text", "")
                index = params.get("index", -1)
                result = engine.type_text(text, index if index >= 0 else None)
                return {"success": True, "message": result}
            elif action_type == "hotkey":
                keys = params.get("keys", [])
                result = engine.hotkey(keys)
                return {"success": True, "message": result}
            elif action_type == "press_key":
                key = params.get("key", "enter")
                result = engine.press_key(key)
                return {"success": True, "message": result}

            return {"success": False, "error": f"UIA 不支持的操作: {action_type}"}
        except ImportError:
            return {"success": False, "error": "UIA 引擎未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_pyautogui(self, action_type: str, params: Dict) -> Dict:
        """使用 pyautogui 执行"""
        try:
            import pyautogui
            if action_type == "click":
                pyautogui.click(params["x"], params["y"])
            elif action_type == "type":
                pyautogui.typewrite(params["text"])
            elif action_type == "hotkey":
                pyautogui.hotkey(*params["keys"])
            return {"success": True, "engine": "pyautogui"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_win32(self, action_type: str, params: Dict) -> Dict:
        """使用 Win32 API 执行"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if action_type == "click":
                user32.SetCursorPos(params["x"], params["y"])
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                time.sleep(0.01)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
            return {"success": True, "engine": "win32api"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_qt(self, action_type: str, params: Dict) -> Dict:
        """使用 Qt Accessibility 执行"""
        try:
            from .advanced_engines import QtAccessibilityEngine
            engine = QtAccessibilityEngine()
            element = engine.find_element(params.get("name", ""))
            if element:
                engine.click_element(element)
                return {"success": True, "engine": "qt_accessibility"}
            return {"success": False, "error": "元素未找到"}
        except ImportError:
            return {"success": False, "error": "Qt Accessibility 引擎未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_selenium(self, action_type: str, params: Dict) -> Dict:
        """使用 Selenium 执行（浏览器自动化）"""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By

            # 注意：需要传入 driver 实例
            driver = params.get("driver")
            if not driver:
                return {"success": False, "error": "Selenium 需要传入 driver 实例"}

            if action_type == "click":
                selector = params.get("selector", "")
                element = driver.find_element(By.CSS_SELECTOR, selector)
                element.click()
                return {"success": True, "engine": "selenium"}
            elif action_type == "type":
                selector = params.get("selector", "")
                text = params.get("text", "")
                element = driver.find_element(By.CSS_SELECTOR, selector)
                element.send_keys(text)
                return {"success": True, "engine": "selenium"}

            return {"success": False, "error": f"Selenium 不支持的操作: {action_type}"}
        except ImportError:
            return {"success": False, "error": "Selenium 未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}
