"""
AppAgent - 执行层

职责：
1. 执行具体的 UI 操作
2. 智能选择最优执行方式（UIA / pywinauto / pyautogui / Win32 / PIL）
3. 支持降级链
4. 集成持续感知和实体操作

参考 UFO 的 ControlReceiver 设计，专注于 MiMo
借鉴 cellar 的持续感知和 desktop-touch 的实体操作
"""

import time
from typing import Any
from .action_models import Action, ActionType, ActionResult
from .execution_engines import EngineManager, EngineType, TaskCategory
from .continuous_awareness import ContinuousAwareness
from .entity_operations import EntityResolver, EntityExecutor


class AppAgent:
    """
    执行层 - 万能执行引擎

    智能选择执行方式：
    1. 根据任务类别选择最优引擎
    2. 支持降级链（主引擎失败自动切换）
    3. 集成持续感知（边操作边看）
    4. 支持实体操作（语义代替坐标）
    """

    def __init__(self):
        """初始化执行层"""
        self._uia_engine = None
        self._pyautogui = None

        # 新增：执行引擎管理器
        self.engine_manager = EngineManager()

        # 新增：持续感知
        self.awareness = ContinuousAwareness()

        # 新增：实体操作
        self.entity_resolver = EntityResolver()
        self.entity_executor = EntityExecutor()

        # 统一统计系统
        self.stats = {
            "total_actions": 0,
            "success_count": 0,
            "failure_count": 0,
            "avg_duration": 0,
            "engine_stats": {},
            "error_types": {},
            "action_types": {},
        }

    def _ensure_uia(self):
        """确保 UIA 引擎可用"""
        if self._uia_engine is None:
            try:
                from src.uia_engine import UIAEngine
                self._uia_engine = UIAEngine()
            except Exception:
                pass
        return self._uia_engine

    def _ensure_pyautogui(self):
        """确保 pyautogui 可用"""
        if self._pyautogui is None:
            import pyautogui
            self._pyautogui = pyautogui
        return self._pyautogui

    def execute(self, action: Action, uia_tree: Any = None) -> ActionResult:
        """
        执行单个动作

        智能选择执行方式：
        1. 根据任务类别选择最优引擎
        2. 支持降级链（主引擎失败自动切换）
        3. 集成持续感知（边操作边看）

        Args:
            action: 要执行的动作
            uia_tree: 当前 UIA 树（可选）

        Returns:
            ActionResult: 执行结果
        """
        start_time = time.time()
        self.stats["total_actions"] += 1

        # 记录操作类型
        action_type = action.action_type.value
        self.stats["action_types"][action_type] = self.stats["action_types"].get(action_type, 0) + 1

        try:
            # 获取当前界面快照（持续感知）
            snapshot = self.awareness.take_snapshot()

            # 基础操作
            if action.action_type == ActionType.CLICK:
                result = self._execute_click(action, uia_tree)
            elif action.action_type == ActionType.DOUBLE_CLICK:
                result = self._execute_double_click(action, uia_tree)
            elif action.action_type == ActionType.TYPE_TEXT:
                result = self._execute_type_text(action, uia_tree)
            elif action.action_type == ActionType.PRESS_KEY:
                result = self._execute_press_key(action)
            elif action.action_type == ActionType.HOTKEY:
                result = self._execute_hotkey(action)
            elif action.action_type == ActionType.SCROLL:
                result = self._execute_scroll(action)
            elif action.action_type == ActionType.WAIT:
                result = self._execute_wait(action)
            elif action.action_type == ActionType.DRAG:
                result = self._execute_drag(action)
            # 绘制操作（智能选择引擎）
            elif action.action_type == ActionType.DRAW_PATH:
                result = self._execute_draw_path(action)
            elif action.action_type == ActionType.DRAW_CURVE:
                result = self._execute_draw_curve(action)
            elif action.action_type == ActionType.DRAW_CIRCLE:
                result = self._execute_draw_circle(action)
            elif action.action_type == ActionType.DRAW_PRECISE:
                result = self._execute_draw_precise(action)
            elif action.action_type == ActionType.DRAW_BATCH:
                result = self._execute_draw_batch(action)
            else:
                result = ActionResult(
                    action=action,
                    success=False,
                    message=f"不支持的操作类型: {action.action_type}"
                )

            # 更新统计
            duration = time.time() - start_time
            if result.success:
                self.stats["success_count"] += 1
            else:
                self.stats["failure_count"] += 1
                # 记录错误类型
                error_type = self._classify_error(result.message)
                self.stats["error_types"][error_type] = self.stats["error_types"].get(error_type, 0) + 1

            # 更新平均耗时
            total = self.stats["total_actions"]
            old_avg = self.stats["avg_duration"]
            self.stats["avg_duration"] = (old_avg * (total - 1) + duration) / total

            return result

        except Exception as e:
            self.stats["failure_count"] += 1
            # 记录错误类型
            error_type = self._classify_error(str(e))
            self.stats["error_types"][error_type] = self.stats["error_types"].get(error_type, 0) + 1
            return ActionResult(
                action=action,
                success=False,
                message=f"执行失败: {e}"
            )

    def _execute_click(self, action: Action, uia_tree: Any) -> ActionResult:
        """
        点击操作 - 智能选择执行方式

        优先级：
        1. UIA 控件直接点击（最稳定）
        2. 坐标点击（降级）
        """
        index = action.params.get("index", action.target_index)

        # 方式 1：通过 UIA 控件直接点击
        if index >= 0 and uia_tree:
            engine = self._ensure_uia()
            if engine:
                result = engine.click_node(index)
                if "成功" in result or "已点击" in result:
                    return ActionResult(
                        action=action,
                        success=True,
                        message=result
                    )

        # 方式 2：降级到坐标点击
        if index >= 0 and uia_tree and hasattr(uia_tree, 'nodes'):
            if index < len(uia_tree.nodes):
                node = uia_tree.nodes[index]
                if node.rect:
                    cx = (node.rect[0] + node.rect[2]) // 2
                    cy = (node.rect[1] + node.rect[3]) // 2
                    pyautogui = self._ensure_pyautogui()
                    if pyautogui:
                        pyautogui.click(cx, cy)
                        return ActionResult(
                            action=action,
                            success=True,
                            message=f"通过坐标点击: ({cx}, {cy})"
                        )

        return ActionResult(
            action=action,
            success=False,
            message="无法定位控件"
        )

    def _execute_double_click(self, action: Action, uia_tree: Any) -> ActionResult:
        """双击操作"""
        index = action.params.get("index", action.target_index)
        pyautogui = self._ensure_pyautogui()

        if index >= 0 and uia_tree and hasattr(uia_tree, 'nodes'):
            if index < len(uia_tree.nodes):
                node = uia_tree.nodes[index]
                if node.rect:
                    cx = (node.rect[0] + node.rect[2]) // 2
                    cy = (node.rect[1] + node.rect[3]) // 2

                    # 记住当前前台窗口（防止焦点跳走）
                    try:
                        import win32gui
                        original_window = win32gui.GetForegroundWindow()
                    except (ImportError, Exception):
                        original_window = None

                    if pyautogui:
                        pyautogui.doubleClick(cx, cy)

                    # 重新激活原窗口
                    if original_window:
                        time.sleep(0.1)
                        try:
                            import win32gui
                            win32gui.SetForegroundWindow(original_window)
                        except (ImportError, Exception):
                            pass

                    return ActionResult(
                        action=action,
                        success=True,
                        message=f"双击: ({cx}, {cy})"
                    )

        return ActionResult(
            action=action,
            success=False,
            message="无法定位控件"
        )

    def _execute_type_text(self, action: Action, uia_tree: Any) -> ActionResult:
        """输入文字"""
        text = action.params.get("text", "")
        index = action.params.get("index", action.target_index)

        engine = self._ensure_uia()
        if engine:
            result = engine.type_text(text, index if index >= 0 else None)
            return ActionResult(
                action=action,
                success=True,
                message=result
            )

        # 降级：pyautogui
        pyautogui = self._ensure_pyautogui()
        if pyautogui:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return ActionResult(
                action=action,
                success=True,
                message=f"通过剪贴板输入: {text[:50]}"
            )

        return ActionResult(
            action=action,
            success=False,
            message="输入失败"
        )

    def _execute_press_key(self, action: Action) -> ActionResult:
        """按键"""
        key = action.params.get("key", "")
        engine = self._ensure_uia()
        if engine:
            result = engine.press_key(key)
            return ActionResult(
                action=action,
                success=True,
                message=result
            )

        return ActionResult(
            action=action,
            success=False,
            message="按键失败"
        )

    def _execute_hotkey(self, action: Action) -> ActionResult:
        """组合键"""
        keys = action.params.get("keys", [])
        engine = self._ensure_uia()
        if engine:
            result = engine.hotkey(keys)
            return ActionResult(
                action=action,
                success=True,
                message=result
            )

        return ActionResult(
            action=action,
            success=False,
            message="组合键失败"
        )

    def _execute_scroll(self, action: Action) -> ActionResult:
        """滚动"""
        direction = action.params.get("direction", "down")
        clicks = 3 if direction == "up" else -3

        pyautogui = self._ensure_pyautogui()
        if pyautogui:
            pyautogui.scroll(clicks)
            return ActionResult(
                action=action,
                success=True,
                message=f"滚动: {direction}"
            )

        return ActionResult(
            action=action,
            success=False,
            message="滚动失败"
        )

    def _execute_wait(self, action: Action) -> ActionResult:
        """等待"""
        seconds = action.params.get("seconds", 1)
        time.sleep(seconds)
        return ActionResult(
            action=action,
            success=True,
            message=f"等待 {seconds} 秒"
        )

    def _execute_drag(self, action: Action) -> ActionResult:
        """拖拽"""
        start_x = action.params.get("start_x", 0)
        start_y = action.params.get("start_y", 0)
        end_x = action.params.get("end_x", 0)
        end_y = action.params.get("end_y", 0)

        pyautogui = self._ensure_pyautogui()
        if pyautogui:
            pyautogui.moveTo(start_x, start_y)
            pyautogui.mouseDown()
            pyautogui.moveTo(end_x, end_y, duration=0.5)
            pyautogui.mouseUp()
            return ActionResult(
                action=action,
                success=True,
                message=f"拖拽: ({start_x},{start_y}) -> ({end_x},{end_y})"
            )

        return ActionResult(
            action=action,
            success=False,
            message="拖拽失败"
        )

    # ============================================================
    # 智能绘制方法
    # ============================================================

    def _execute_draw_path(self, action: Action) -> ActionResult:
        """
        手绘路径 - 根据 engine 参数选择执行方式

        engine="pyautogui": 简单绘制
        engine="win32": 精细绘制，可模拟压感
        """
        points = action.params.get("points", [])
        engine = action.params.get("engine", "pyautogui")
        speed = action.params.get("speed", 0.01)

        if not points or len(points) < 2:
            return ActionResult(
                action=action,
                success=False,
                message="至少需要 2 个点"
            )

        if engine == "win32":
            return self._draw_path_win32(action, points, speed)
        else:
            return self._draw_path_pyautogui(action, points, speed)

    def _draw_path_pyautogui(self, action: Action, points: list, speed: float) -> ActionResult:
        """使用 pyautogui 绘制路径"""
        pyautogui = self._ensure_pyautogui()
        if not pyautogui:
            return ActionResult(action=action, success=False, message="pyautogui 不可用")

        try:
            pyautogui.moveTo(points[0][0], points[0][1])
            pyautogui.mouseDown()
            for point in points[1:]:
                pyautogui.moveTo(point[0], point[1])
                time.sleep(speed)
            pyautogui.mouseUp()

            return ActionResult(
                action=action,
                success=True,
                message=f"pyautogui 绘制完成: {len(points)} 个点"
            )
        except Exception as e:
            return ActionResult(action=action, success=False, message=f"绘制失败: {e}")

    def _draw_path_win32(self, action: Action, points: list, speed: float) -> ActionResult:
        """
        使用 Win32 API 绘制路径（可模拟压感）

        通过控制移动速度模拟线条粗细：
        - 快速移动 = 细线
        - 慢速移动 = 粗线
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32

            # 鼠标事件常量
            MOUSEEVENTF_LEFTDOWN = 0x0002
            MOUSEEVENTF_LEFTUP = 0x0004
            MOUSEEVENTF_MOVE = 0x0001

            # 获取速度曲线参数
            speed_curve = action.params.get("speed_curve", "constant")
            # fast-slow-fast: 两端快中间慢（适合画弧线）
            # slow-fast-slow: 两端慢中间快（适合画直线）
            # constant: 匀速

            # 移动到起点
            user32.SetCursorPos(points[0][0], points[0][1])
            time.sleep(0.01)

            # 按下鼠标
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

            # 绘制路径
            for i, point in enumerate(points[1:]):
                # 根据速度曲线计算当前速度
                if speed_curve == "fast-slow-fast":
                    # 两端快中间慢
                    progress = i / max(len(points) - 2, 1)
                    factor = 1.0 - 4.0 * (progress - 0.5) ** 2  # 抛物线
                    current_speed = speed * (0.5 + factor)
                elif speed_curve == "slow-fast-slow":
                    # 两端慢中间快
                    progress = i / max(len(points) - 2, 1)
                    factor = 4.0 * (progress - 0.5) ** 2  # 抛物线
                    current_speed = speed * (0.5 + factor)
                else:
                    current_speed = speed

                # 移动鼠标
                user32.SetCursorPos(point[0], point[1])
                time.sleep(max(current_speed, 0.001))

            # 释放鼠标
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

            return ActionResult(
                action=action,
                success=True,
                message=f"Win32 绘制完成: {len(points)} 个点, 速度曲线: {speed_curve}"
            )
        except Exception as e:
            return ActionResult(action=action, success=False, message=f"Win32 绘制失败: {e}")

    def _execute_draw_curve(self, action: Action) -> ActionResult:
        """贝塞尔曲线绘制"""
        import math

        start = action.params.get("start", [0, 0])
        end = action.params.get("end", [0, 0])
        control = action.params.get("control", [0, 0])
        segments = action.params.get("segments", 20)
        engine = action.params.get("engine", "pyautogui")

        # 生成贝塞尔曲线点
        points = []
        for i in range(segments + 1):
            t = i / segments
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control[0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control[1] + t**2 * end[1]
            points.append([int(x), int(y)])

        # 复用 draw_path 执行
        draw_action = Action(
            action_type=ActionType.DRAW_PATH,
            params={"points": points, "engine": engine, "speed": action.params.get("speed", 0.01)},
            description=action.description
        )
        return self._execute_draw_path(draw_action)

    def _execute_draw_circle(self, action: Action) -> ActionResult:
        """圆形绘制"""
        import math

        center = action.params.get("center", [0, 0])
        radius = action.params.get("radius", 50)
        segments = action.params.get("segments", 36)
        engine = action.params.get("engine", "pyautogui")

        # 生成圆形点
        points = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            points.append([int(x), int(y)])

        # 复用 draw_path 执行
        draw_action = Action(
            action_type=ActionType.DRAW_PATH,
            params={"points": points, "engine": engine, "speed": action.params.get("speed", 0.01)},
            description=action.description
        )
        return self._execute_draw_path(draw_action)

    def _execute_draw_precise(self, action: Action) -> ActionResult:
        """
        精细绘制 - 专门用于素描等需要压感的场景

        自动使用 Win32 API，支持：
        - 速度曲线控制
        - 多次叠加
        - 渐变效果
        """
        # 强制使用 Win32 引擎
        action.params["engine"] = "win32"
        return self._execute_draw_path(action)

    def _execute_draw_batch(self, action: Action) -> ActionResult:
        """
        批量绘制 - 使用 PIL 直接生成图片

        适用于：
        - 重复图案
        - 几何图形
        - 批量处理
        """
        try:
            from PIL import Image, ImageDraw

            width = action.params.get("width", 800)
            height = action.params.get("height", 600)
            elements = action.params.get("elements", [])
            output_path = action.params.get("output_path", "output.png")

            # 创建画布
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)

            # 绘制每个元素
            for elem in elements:
                elem_type = elem.get("type", "")

                if elem_type == "line":
                    # 直线
                    x1, y1 = elem.get("start", [0, 0])
                    x2, y2 = elem.get("end", [0, 0])
                    color = elem.get("color", "black")
                    width_line = elem.get("width", 1)
                    draw.line([(x1, y1), (x2, y2)], fill=color, width=width_line)

                elif elem_type == "ellipse":
                    # 椭圆
                    cx, cy = elem.get("center", [0, 0])
                    rx, ry = elem.get("radius", [50, 50])
                    color = elem.get("color", "black")
                    draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], outline=color)

                elif elem_type == "rectangle":
                    # 矩形
                    x, y = elem.get("pos", [0, 0])
                    w, h = elem.get("size", [100, 100])
                    color = elem.get("color", "black")
                    draw.rectangle([x, y, x+w, y+h], outline=color)

                elif elem_type == "path":
                    # 路径
                    points = elem.get("points", [])
                    color = elem.get("color", "black")
                    if len(points) >= 2:
                        draw.line(points, fill=color)

            # 保存图片
            img.save(output_path)

            return ActionResult(
                action=action,
                success=True,
                message=f"PIL 批量绘制完成: {len(elements)} 个元素, 保存到 {output_path}"
            )
        except Exception as e:
            return ActionResult(action=action, success=False, message=f"PIL 绘制失败: {e}")

    # ============================================================
    # 统计和信息方法
    # ============================================================

    def _classify_error(self, error_message: str) -> str:
        """分类错误类型"""
        error_lower = error_message.lower()

        if "timeout" in error_lower or "timed out" in error_lower:
            return "timeout"
        elif "permission" in error_lower or "access denied" in error_lower:
            return "permission"
        elif "not found" in error_lower or "no such" in error_lower:
            return "not_found"
        elif "connection" in error_lower or "network" in error_lower:
            return "network"
        elif "element" in error_lower or "control" in error_lower:
            return "ui_error"
        elif "import" in error_lower or "module" in error_lower:
            return "import_error"
        else:
            return "other"

    def get_stats(self) -> dict:
        """获取操作统计"""
        total = self.stats["total_actions"]
        success = self.stats["success_count"]
        failure = self.stats["failure_count"]

        return {
            "total_actions": total,
            "success_count": success,
            "failure_count": failure,
            "success_rate": success / total if total > 0 else 0,
            "avg_duration": self.stats["avg_duration"],
            "engine_stats": self.engine_manager.get_stats(),
            "error_types": self.stats["error_types"],
            "action_types": self.stats["action_types"],
        }

    def get_available_engines(self) -> list:
        """获取所有可用引擎"""
        return self.engine_manager.get_available_engines()

    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_actions": 0,
            "success_count": 0,
            "failure_count": 0,
            "avg_duration": 0,
            "engine_stats": {},
            "error_types": {},
            "action_types": {},
        }
