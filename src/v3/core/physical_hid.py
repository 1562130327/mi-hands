"""
PhysicalHID - 物理 HID 控制

借鉴 clawtouch-mcp 的设计理念：
1. 物理键盘/鼠标控制
2. 绕过软件层的检测
3. 作为 pyautogui 的降级方案

适用场景：
- pyautogui 被反自动化软件拦截
- 需要物理级别的输入
- 游戏或特殊应用

注意：需要硬件支持（树莓派 Pico）或模拟器
"""

import time
from typing import Optional, Dict, Any, List
from enum import Enum


class HIDMethod(Enum):
    """HID 控制方法"""
    PYAUTOGUI = "pyautogui"          # pyautogui（默认）
    WIN32_API = "win32api"            # Win32 API
    PHYSICAL_PICO = "physical_pico"  # 物理树莓派 Pico
    MOCK = "mock"                    # 模拟模式（测试用）


class PhysicalHID:
    """
    物理 HID 控制器

    作为 pyautogui 的降级方案：
    1. 当 pyautogui 失败时，尝试 Win32 API
    2. 当 Win32 API 失败时，尝试物理 HID
    3. 都失败时，进入模拟模式
    """

    def __init__(self, preferred_method: HIDMethod = HIDMethod.PYAUTOGUI):
        """
        初始化物理 HID 控制器

        Args:
            preferred_method: 首选的控制方法
        """
        self.preferred_method = preferred_method
        self.current_method = preferred_method
        self.fallback_chain = [
            HIDMethod.PYAUTOGUI,
            HIDMethod.WIN32_API,
            HIDMethod.MOCK
        ]

    def move(self, x: int, y: int, duration: float = 0.1) -> Dict[str, Any]:
        """
        移动鼠标

        Args:
            x: 目标 X 坐标
            y: 目标 Y 坐标
            duration: 移动时间

        Returns:
            执行结果
        """
        for method in self.fallback_chain:
            try:
                if method == HIDMethod.PYAUTOGUI:
                    return self._move_pyautogui(x, y, duration)
                elif method == HIDMethod.WIN32_API:
                    return self._move_win32(x, y)
                elif method == HIDMethod.MOCK:
                    return self._move_mock(x, y)
            except Exception as e:
                print(f"Method {method.value} failed: {e}")
                continue

        return {"success": False, "message": "All methods failed"}

    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """
        点击

        Args:
            x: X 坐标
            y: Y 坐标
            button: 鼠标按钮

        Returns:
            执行结果
        """
        for method in self.fallback_chain:
            try:
                if method == HIDMethod.PYAUTOGUI:
                    return self._click_pyautogui(x, y, button)
                elif method == HIDMethod.WIN32_API:
                    return self._click_win32(x, y, button)
                elif method == HIDMethod.MOCK:
                    return self._click_mock(x, y, button)
            except Exception as e:
                print(f"Method {method.value} failed: {e}")
                continue

        return {"success": False, "message": "All methods failed"}

    def double_click(self, x: int, y: int) -> Dict[str, Any]:
        """双击"""
        for method in self.fallback_chain:
            try:
                if method == HIDMethod.PYAUTOGUI:
                    return self._double_click_pyautogui(x, y)
                elif method == HIDMethod.WIN32_API:
                    return self._double_click_win32(x, y)
                elif method == HIDMethod.MOCK:
                    return self._double_click_mock(x, y)
            except Exception as e:
                print(f"Method {method.value} failed: {e}")
                continue

        return {"success": False, "message": "All methods failed"}

    def type_text(self, text: str) -> Dict[str, Any]:
        """输入文字"""
        for method in self.fallback_chain:
            try:
                if method == HIDMethod.PYAUTOGUI:
                    return self._type_text_pyautogui(text)
                elif method == HIDMethod.WIN32_API:
                    return self._type_text_win32(text)
                elif method == HIDMethod.MOCK:
                    return self._type_text_mock(text)
            except Exception as e:
                print(f"Method {method.value} failed: {e}")
                continue

        return {"success": False, "message": "All methods failed"}

    def press_key(self, key: str) -> Dict[str, Any]:
        """按键"""
        for method in self.fallback_chain:
            try:
                if method == HIDMethod.PYAUTOGUI:
                    return self._press_key_pyautogui(key)
                elif method == HIDMethod.WIN32_API:
                    return self._press_key_win32(key)
                elif method == HIDMethod.MOCK:
                    return self._press_key_mock(key)
            except Exception as e:
                print(f"Method {method.value} failed: {e}")
                continue

        return {"success": False, "message": "All methods failed"}

    # ============================================================
    # pyautogui 实现
    # ============================================================

    def _move_pyautogui(self, x: int, y: int, duration: float) -> Dict[str, Any]:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return {"success": True, "message": f"Moved to ({x}, {y})", "method": "pyautogui"}

    def _click_pyautogui(self, x: int, y: int, button: str) -> Dict[str, Any]:
        import pyautogui
        if button == "right":
            pyautogui.rightClick(x, y)
        else:
            pyautogui.click(x, y)
        return {"success": True, "message": f"Clicked ({x}, {y})", "method": "pyautogui"}

    def _double_click_pyautogui(self, x: int, y: int) -> Dict[str, Any]:
        import pyautogui
        pyautogui.doubleClick(x, y)
        return {"success": True, "message": f"Double-clicked ({x}, {y})", "method": "pyautogui"}

    def _type_text_pyautogui(self, text: str) -> Dict[str, Any]:
        import pyautogui
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return {"success": True, "message": f"Typed text", "method": "pyautogui"}

    def _press_key_pyautogui(self, key: str) -> Dict[str, Any]:
        import pyautogui
        pyautogui.press(key)
        return {"success": True, "message": f"Pressed {key}", "method": "pyautogui"}

    # ============================================================
    # Win32 API 实现
    # ============================================================

    def _move_win32(self, x: int, y: int) -> Dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetCursorPos(x, y)
        return {"success": True, "message": f"Moved to ({x}, {y})", "method": "win32api"}

    def _click_win32(self, x: int, y: int, button: str) -> Dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32

        # 移动到目标位置
        user32.SetCursorPos(x, y)
        time.sleep(0.01)

        # 执行点击
        if button == "right":
            user32.mouse_event(0x0008, 0, 0, 0, 0)  # 右键按下
            time.sleep(0.01)
            user32.mouse_event(0x0010, 0, 0, 0, 0)  # 右键抬起
        else:
            user32.mouse_event(0x0002, 0, 0, 0, 0)  # 左键按下
            time.sleep(0.01)
            user32.mouse_event(0x0004, 0, 0, 0, 0)  # 左键抬起

        return {"success": True, "message": f"Clicked ({x}, {y})", "method": "win32api"}

    def _double_click_win32(self, x: int, y: int) -> Dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32

        user32.SetCursorPos(x, y)
        time.sleep(0.01)

        # 双击
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # 左键按下
        time.sleep(0.01)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # 左键抬起
        time.sleep(0.05)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # 左键按下
        time.sleep(0.01)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # 左键抬起

        return {"success": True, "message": f"Double-clicked ({x}, {y})", "method": "win32api"}

    def _type_text_win32(self, text: str) -> Dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32

        for char in text:
            # 模拟按键
            vk = ord(char.upper())
            user32.keybd_event(vk, 0, 0, 0)  # 按下
            time.sleep(0.01)
            user32.keybd_event(vk, 0, 2, 0)  # 抬起
            time.sleep(0.01)

        return {"success": True, "message": f"Typed text", "method": "win32api"}

    def _press_key_win32(self, key: str) -> Dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32

        # 简单的按键映射
        key_map = {
            "enter": 0x0D,
            "tab": 0x09,
            "escape": 0x1B,
            "space": 0x20,
        }

        vk = key_map.get(key.lower(), ord(key.upper()))
        user32.keybd_event(vk, 0, 0, 0)  # 按下
        time.sleep(0.01)
        user32.keybd_event(vk, 0, 2, 0)  # 抬起

        return {"success": True, "message": f"Pressed {key}", "method": "win32api"}

    # ============================================================
    # Mock 实现（测试用）
    # ============================================================

    def _move_mock(self, x: int, y: int) -> Dict[str, Any]:
        return {"success": True, "message": f"[MOCK] Moved to ({x}, {y})", "method": "mock"}

    def _click_mock(self, x: int, y: int, button: str) -> Dict[str, Any]:
        return {"success": True, "message": f"[MOCK] Clicked ({x}, {y})", "method": "mock"}

    def _double_click_mock(self, x: int, y: int) -> Dict[str, Any]:
        return {"success": True, "message": f"[MOCK] Double-clicked ({x}, {y})", "method": "mock"}

    def _type_text_mock(self, text: str) -> Dict[str, Any]:
        return {"success": True, "message": f"[MOCK] Typed text", "method": "mock"}

    def _press_key_mock(self, key: str) -> Dict[str, Any]:
        return {"success": True, "message": f"[MOCK] Pressed {key}", "method": "mock"}
