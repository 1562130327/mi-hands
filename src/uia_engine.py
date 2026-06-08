"""
UIA 引擎 — 控件树读取 + 输入注入 + 截图 + 窗口管理

核心思路：
- 用 uiautomation 读取 Windows 控件树（比截图便宜 60-75% tokens）
- 过滤掉装饰性元素，只保留可交互/可读的控件
- 支持 diff 更新，第二轮起只返回变化部分
"""

import time
import base64
import io
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import uiautomation as auto
import pyautogui
from PIL import Image


# ============================================================
# 数据结构
# ============================================================

@dataclass
class UINode:
    """精简后的 UI 控件节点"""
    index: int  # 在精简树中的序号（给 AI 引用）
    control_type: str  # Button / Edit / Text / Hyperlink 等
    name: str  # 控件显示名称
    value: str = ""  # 当前值（如输入框内容）
    is_enabled: bool = True
    is_focused: bool = False
    rect: tuple = ()  # (left, top, right, bottom)
    runtime_id: str = ""  # 用于唯一定位控件

    def to_text(self) -> str:
        """转成 AI 可读的文本格式"""
        parts = [f"[{self.index}] {self.control_type}"]
        if self.name:
            parts.append(f'"{self.name}"')
        if self.value:
            parts.append(f'value="{self.value}"')
        if self.is_focused:
            parts.append("(focused)")
        return " ".join(parts)


@dataclass
class UITree:
    """完整的 UI 树快照"""
    window_title: str
    window_handle: int
    nodes: list[UINode]
    timestamp: float
    tree_hash: str = ""  # 用于 diff 检测

    def __post_init__(self):
        if not self.tree_hash:
            self.tree_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = "|".join(n.to_text() for n in self.nodes)
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def to_text(self) -> str:
        """转成给 AI 看的文本"""
        lines = [f"窗口: {self.window_title}"]
        for node in self.nodes:
            lines.append(node.to_text())
        return "\n".join(lines)

    def diff(self, old: "UITree") -> str:
        """只返回变化的部分"""
        if self.tree_hash == old.tree_hash:
            return "(UI 树无变化)"

        old_nodes = {n.runtime_id: n for n in old.nodes}
        new_nodes = {n.runtime_id: n for n in self.nodes}

        added = [n for rid, n in new_nodes.items() if rid not in old_nodes]
        removed = [n for rid, n in old_nodes.items() if rid not in new_nodes]
        changed = []
        for rid in new_nodes:
            if rid in old_nodes and new_nodes[rid].to_text() != old_nodes[rid].to_text():
                changed.append(new_nodes[rid])

        lines = []
        if added:
            lines.append("新增:")
            lines.extend(f"  + {n.to_text()}" for n in added)
        if removed:
            lines.append("移除:")
            lines.extend(f"  - {n.to_text()}" for n in removed)
        if changed:
            lines.append("变化:")
            lines.extend(f"  ~ {n.to_text()}" for n in changed)
        return "\n".join(lines) if lines else "(UI 树无实质变化)"


@dataclass
class Screenshot:
    """截图数据"""
    base64_data: str
    width: int
    height: int
    timestamp: float


# ============================================================
# 可交互控件类型
# ============================================================

# 保留这些类型的控件（AI 需要看到或操作的）
KEEP_TYPES = {
    "Button", "Edit", "Hyperlink", "Text", "CheckBox", "RadioButton",
    "ComboBox", "ListItem", "MenuItem", "TabItem", "TreeItem",
    "Slider", "Spinner", "ToolBar", "MenuBar", "ScrollBar",
    "DataItem", "Header", "HeaderItem", "SplitButton",
}

# 跳过这些类型（装饰性、不可操作）
SKIP_TYPES = {
    "Pane", "Group", "Document", "Window", "Custom",
    "Table", "List", "ToolBar", "MenuBar",
}

# 跳过没有名称且不是输入框的控件
SKIP_EMPTY_NAME_TYPES = {"Text", "Pane", "Group", "Document", "Image", "ImageControl"}


# ============================================================
# UIA 引擎
# ============================================================

class UIAEngine:
    """UIA 控件树引擎"""

    def __init__(self, max_nodes: int = 50):
        self.max_nodes = max_nodes
        self._last_tree: Optional[UITree] = None
        # pyautogui 安全设置
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

    # ----------------------------------------------------------
    # 控件树
    # ----------------------------------------------------------

    def get_tree(self, window_handle: Optional[int] = None, use_diff: bool = True) -> UITree:
        """获取当前窗口的精简 UI 树"""
        if window_handle:
            control = auto.ControlFromHandle(window_handle)
        else:
            # 方法1：获取前台窗口（最可靠）
            try:
                import win32gui
                fg_hwnd = win32gui.GetForegroundWindow()
                if fg_hwnd:
                    control = auto.ControlFromHandle(fg_hwnd)
                    if control and control.ClassName in ("Shell_TrayWnd", "NotifyIconOverflowWindow"):
                        control = None
            except Exception:
                control = None

            # 方法2：降级到焦点控件向上找
            if not control:
                try:
                    control = auto.GetFocusedControl()
                    while control and control.GetParentControl():
                        parent = control.GetParentControl()
                        if parent.ClassName in ("Shell_TrayWnd", "NotifyIconOverflowWindow"):
                            break
                        control = parent
                except Exception:
                    control = None

        if not control:
            return UITree(window_title="(无法获取)", window_handle=0, nodes=[], timestamp=time.time())

        window_title = control.Name or "(无标题)"
        window_handle = control.NativeWindowHandle or 0

        nodes = self._walk_tree(control)
        # 统一分配索引
        for i, node in enumerate(nodes[:self.max_nodes]):
            node.index = i
        tree = UITree(
            window_title=window_title,
            window_handle=window_handle,
            nodes=nodes[:self.max_nodes],
            timestamp=time.time(),
        )
        return tree

    def get_snapshot(self, window_handle: Optional[int] = None) -> str:
        """获取可读的 UI 树文本（给 AI 看的）"""
        tree = self.get_tree(window_handle)
        if self._last_tree and self._last_tree.tree_hash == tree.tree_hash:
            return f"窗口: {tree.window_title}\n(UI 树无变化)"

        result = tree.to_text()
        self._last_tree = tree
        return result

    def get_diff(self, window_handle: Optional[int] = None) -> str:
        """获取与上次快照的差异"""
        tree = self.get_tree(window_handle)
        if not self._last_tree:
            result = tree.to_text()
            self._last_tree = tree
            return result

        diff = tree.diff(self._last_tree)
        self._last_tree = tree
        return diff

    def _walk_tree(self, control, depth: int = 0, max_depth: int = 6) -> list[UINode]:
        """递归遍历控件树，提取有意义的节点"""
        nodes = []
        if depth > max_depth:
            return nodes

        try:
            children = control.GetChildren()
        except Exception:
            return nodes

        for child in children:
            try:
                node = self._extract_node(child)
                if node:
                    nodes.append(node)

                # 容器类型：继续深入，但不额外加节点
                ct = child.ControlTypeName
                should_dive = ct in (
                    "Pane", "Group", "ToolBar", "List", "Tree",
                    "MenuBar", "Tab", "Header", "DataGrid",
                    "Edit", "ComboBox", "Window",
                )
                if should_dive or child.GetChildren():
                    nodes.extend(self._walk_tree(child, depth + 1, max_depth))
            except Exception:
                continue

        return nodes

    def _extract_node(self, control) -> Optional[UINode]:
        """从 UIA 控件中提取精简信息"""
        try:
            ct = control.ControlTypeName
            name = control.Name or ""

            # 过滤规则
            if ct in SKIP_TYPES:
                return None
            if ct in SKIP_EMPTY_NAME_TYPES and not name:
                return None
            if not ct:
                return None
            # 跳过纯装饰的 Image 控件
            if ct in ("Image", "ImageControl") and not name:
                return None

            # 提取值
            value = ""
            try:
                value = control.GetValuePattern().Value if control.GetValuePattern() else ""
            except Exception:
                pass

            # 提取位置
            rect = ()
            try:
                r = control.BoundingRectangle
                if r:
                    rect = (int(r.left), int(r.top), int(r.right), int(r.bottom))
            except Exception:
                pass

            # 构造 runtime_id 用于唯一定位
            runtime_id = ""
            try:
                rid = control.GetRuntimeId()
                runtime_id = "-".join(str(x) for x in rid) if rid else ""
            except Exception:
                runtime_id = f"{ct}-{name}-{rect}"

            return UINode(
                index=0,  # 稍后统一分配
                control_type=ct,
                name=name,
                value=value,
                is_enabled=control.IsEnabled,
                is_focused=control.HasKeyboardFocus,
                rect=rect,
                runtime_id=runtime_id,
            )
        except Exception:
            return None

    # ----------------------------------------------------------
    # 输入操作
    # ----------------------------------------------------------

    def click(self, x: int, y: int, button: str = "left") -> str:
        """点击指定坐标"""
        try:
            pyautogui.click(x, y, button=button)
            return f"已点击 ({x}, {y})"
        except Exception as e:
            return f"点击失败: {e}"

    def click_node(self, index: int) -> str:
        """通过 UI 树索引点击控件（优先用 pyautogui 真实鼠标点击）"""
        if not self._last_tree or index < 0 or index >= len(self._last_tree.nodes):
            return f"无效的控件索引: {index}"

        node = self._last_tree.nodes[index]
        if not node.rect:
            return f"控件 [{index}] 没有位置信息"

        # 优先用 pyautogui 真实鼠标点击（最可靠，模拟人类操作）
        cx = (node.rect[0] + node.rect[2]) // 2
        cy = (node.rect[1] + node.rect[3]) // 2
        pyautogui.click(cx, cy)
        return f"已点击 [{index}] {node.name} ({cx}, {cy})"

    def type_text(self, text: str, index: Optional[int] = None) -> str:
        """输入文字。如果指定 index，先点击该控件再输入"""
        try:
            if index is not None and self._last_tree:
                if 0 <= index < len(self._last_tree.nodes):
                    node = self._last_tree.nodes[index]
                    # 尝试用 UIA SetValue（最快最准）
                    try:
                        control = auto.ControlFromHandle(self._last_tree.window_handle)
                        if control:
                            target = self._find_control_by_runtime_id(control, node.runtime_id)
                            if target:
                                try:
                                    vp = target.GetValuePattern()
                                    if vp:
                                        vp.SetValue(text)
                                        return f"已通过 UIA 设置值 [{index}]: {text[:50]}"
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    # 降级：点击 + 粘贴
                    self.click_node(index)

            # 用剪贴板粘贴（比 pyautogui.typewrite 支持中文）
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return f"已输入: {text[:50]}{'...' if len(text) > 50 else ''}"
        except Exception as e:
            return f"输入失败: {e}"

    def press_key(self, key: str) -> str:
        """按键"""
        try:
            pyautogui.press(key)
            # 某些按键（如 enter）会触发 UI 变化，等一下再返回
            if key.lower() in ("enter", "return", "escape", "tab", "space"):
                time.sleep(0.3)
            return f"已按键: {key}"
        except Exception as e:
            return f"按键失败: {e}"

    def hotkey(self, keys: list[str]) -> str:
        """组合键"""
        try:
            pyautogui.hotkey(*keys)
            # 组合键通常会触发 UI 变化
            time.sleep(0.3)
            return f"已按组合键: {'+'.join(keys)}"
        except Exception as e:
            return f"组合键失败: {e}"

    def scroll(self, x: int, y: int, delta: int) -> str:
        """滚动。delta 正数向上，负数向下"""
        try:
            pyautogui.scroll(delta, x, y)
            return f"已在 ({x}, {y}) 滚动 {delta}"
        except Exception as e:
            return f"滚动失败: {e}"

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """拖拽"""
        try:
            pyautogui.moveTo(x1, y1)
            pyautogui.drag(x2 - x1, y2 - y1, duration=0.5)
            return f"已拖拽 ({x1},{y1}) → ({x2},{y2})"
        except Exception as e:
            return f"拖拽失败: {e}"

    def draw_path(self, points: list[tuple[int, int]], speed: float = 0.01) -> str:
        """
        像人一样手绘路径 — 按住鼠标连续移动

        参数：
            points: 路径点列表 [(x1,y1), (x2,y2), ...]
            speed: 每个点之间的延迟（秒），控制绘制速度

        原理：
            1. 移动到起点
            2. 按下鼠标
            3. 连续移动到每个点（模拟人手移动）
            4. 释放鼠标
        """
        try:
            if not points or len(points) < 2:
                return "路径至少需要 2 个点"

            # 移动到起点
            start_x, start_y = points[0]
            pyautogui.moveTo(start_x, start_y)

            # 按下鼠标
            pyautogui.mouseDown()

            # 连续移动到每个点
            for i, (x, y) in enumerate(points[1:], 1):
                pyautogui.moveTo(x, y)
                time.sleep(speed)

            # 释放鼠标
            pyautogui.mouseUp()

            return f"已绘制路径，共 {len(points)} 个点"
        except Exception as e:
            # 确保鼠标释放
            try:
                pyautogui.mouseUp()
            except:
                pass
            return f"绘制路径失败: {e}"

    def draw_curve(self, start: tuple[int, int], end: tuple[int, int],
                   control: tuple[int, int], segments: int = 20, speed: float = 0.01) -> str:
        """
        绘制贝塞尔曲线 — 用于画弧线、圆角等

        参数：
            start: 起点 (x, y)
            end: 终点 (x, y)
            control: 控制点 (x, y) — 决定曲线弯曲程度
            segments: 分段数，越多越平滑
            speed: 每个点之间的延迟（秒）
        """
        try:
            # 生成贝塞尔曲线点
            points = []
            for i in range(segments + 1):
                t = i / segments
                # 二次贝塞尔公式：B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
                x = int((1-t)**2 * start[0] + 2*(1-t)*t * control[0] + t**2 * end[0])
                y = int((1-t)**2 * start[1] + 2*(1-t)*t * control[1] + t**2 * end[1])
                points.append((x, y))

            # 用 draw_path 绘制
            return self.draw_path(points, speed)
        except Exception as e:
            return f"绘制曲线失败: {e}"

    def draw_circle(self, center: tuple[int, int], radius: int, segments: int = 36, speed: float = 0.01) -> str:
        """
        绘制圆形 — 用于画小鸡身体等

        参数：
            center: 圆心 (x, y)
            radius: 半径
            segments: 分段数，越多越圆
            speed: 每个点之间的延迟（秒）
        """
        import math
        try:
            # 生成圆形点
            points = []
            for i in range(segments + 1):
                angle = 2 * math.pi * i / segments
                x = int(center[0] + radius * math.cos(angle))
                y = int(center[1] + radius * math.sin(angle))
                points.append((x, y))

            # 用 draw_path 绘制
            return self.draw_path(points, speed)
        except Exception as e:
            return f"绘制圆形失败: {e}"
            return f"拖拽失败: {e}"

    # ----------------------------------------------------------
    # 截图
    # ----------------------------------------------------------

    def take_screenshot(self, window_handle: Optional[int] = None) -> Screenshot:
        """截图并转 base64"""
        try:
            if window_handle:
                # 尝试只截指定窗口
                control = auto.ControlFromHandle(window_handle)
                if control:
                    rect = control.BoundingRectangle
                    if rect:
                        img = pyautogui.screenshot(region=(
                            int(rect.left), int(rect.top),
                            int(rect.right - rect.left), int(rect.bottom - rect.top)
                        ))
                    else:
                        img = pyautogui.screenshot()
                else:
                    img = pyautogui.screenshot()
            else:
                img = pyautogui.screenshot()

            # 压缩到合理大小
            img = self._compress_screenshot(img)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()

            return Screenshot(
                base64_data=b64,
                width=img.width,
                height=img.height,
                timestamp=time.time(),
            )
        except Exception as e:
            return Screenshot(base64_data="", width=0, height=0, timestamp=time.time())

    def _compress_screenshot(self, img: Image.Image, max_width: int = 1920) -> Image.Image:
        """压缩截图到合理大小"""
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        return img

    # ----------------------------------------------------------
    # 窗口管理
    # ----------------------------------------------------------

    def list_windows(self) -> list[dict]:
        """列出所有可见窗口"""
        windows = []
        try:
            for window in auto.GetRootControl().GetChildren():
                try:
                    if not window.IsOffscreen and window.Name:
                        windows.append({
                            "handle": window.NativeWindowHandle,
                            "title": window.Name,
                            "class_name": window.ClassName,
                            "is_focused": window.HasKeyboardFocus,
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return windows

    def activate_window(self, window_handle: int) -> str:
        """激活指定窗口"""
        try:
            control = auto.ControlFromHandle(window_handle)
            if control:
                control.SetFocus()
                # 也用 pyautogui 的方式确保前台
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(window_handle)
                except Exception:
                    pass
                return f"已激活窗口: {control.Name}"
            return f"找不到窗口: {window_handle}"
        except Exception as e:
            return f"激活窗口失败: {e}"

    # ----------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------

    def _find_control_by_runtime_id(self, root, runtime_id: str):
        """通过 runtime_id 在控件树中查找控件"""
        try:
            rid = root.GetRuntimeId()
            if rid and "-".join(str(x) for x in rid) == runtime_id:
                return root
        except Exception:
            pass

        try:
            for child in root.GetChildren():
                result = self._find_control_by_runtime_id(child, runtime_id)
                if result:
                    return result
        except Exception:
            pass
        return None


# ============================================================
# 独立测试
# ============================================================

def test_uia():
    """测试 UIA 引擎"""
    import sys
    import io
    # 强制 UTF-8 输出，避免 GBK 编码问题
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    engine = UIAEngine()

    print("=" * 60)
    print("MI Hands - UIA Engine Test")
    print("=" * 60)

    # 列出窗口
    print("\n[Windows List]")
    windows = engine.list_windows()
    for w in windows:
        focus = " <-- focused" if w["is_focused"] else ""
        print(f"  [{w['handle']}] {w['title']}{focus}")

    # 获取当前焦点窗口的 UI 树
    print("\n[UI Tree - Current Focused Window]")
    tree = engine.get_tree()
    print(f"  Window: {tree.window_title}")
    print(f"  Nodes: {len(tree.nodes)}")
    print(f"  Hash: {tree.tree_hash}")
    print()
    for node in tree.nodes:
        print(f"  {node.to_text()}")

    # 测试 diff（读两次）
    print("\n[Diff Test - Read Again]")
    diff = engine.get_diff()
    print(f"  {diff}")

    print("\n[OK] UIA Engine Test Done")


if __name__ == "__main__":
    test_uia()
