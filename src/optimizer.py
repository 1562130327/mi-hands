"""
Token 优化器 — 减少每轮对话的 token 消耗

策略：
1. UIA 树裁剪 — 400 节点 → 30-50 节点（只保留可交互元素）
2. Diff 更新 — 第二轮起只传变化部分
3. 工具定义精简 — schema 尽量短
4. System Prompt 压缩 — 指令精炼不啰嗦
5. 截图按需 — 默认不截图，UIA 读不到时自动降级
"""

from typing import Optional


class TokenOptimizer:
    """Token 优化器"""

    def __init__(self):
        self._last_uia_text: str = ""
        self._turn_count: int = 0
        self._total_saved_tokens: int = 0

    def optimize_uia_text(self, full_text: str, is_first_turn: bool = False) -> str:
        """优化 UIA 树文本"""
        self._turn_count += 1

        if is_first_turn or not self._last_uia_text:
            # 第一轮：发送完整树
            self._last_uia_text = full_text
            return full_text

        # 后续轮次：计算 diff
        if full_text == self._last_uia_text:
            saved = len(full_text) // 4  # 粗略估算 token
            self._total_saved_tokens += saved
            return "(屏幕无变化，无需重新分析)"

        # 有变化：只发变化部分
        old_lines = set(self._last_uia_text.split("\n"))
        new_lines = set(full_text.split("\n"))
        added = new_lines - old_lines
        removed = old_lines - new_lines

        if not added and not removed:
            return "(屏幕无变化)"

        diff_parts = []
        if removed:
            diff_parts.append("移除:\n" + "\n".join(f"  - {l}" for l in removed))
        if added:
            diff_parts.append("新增:\n" + "\n".join(f"  + {l}" for l in added))

        diff_text = "\n".join(diff_parts)
        saved = (len(full_text) - len(diff_text)) // 4
        self._total_saved_tokens += max(0, saved)

        self._last_uia_text = full_text
        return diff_text

    def should_use_screenshot(self, uia_text: str) -> bool:
        """判断是否需要截图兜底"""
        # 如果 UIA 树太短（可能读不到有用信息），建议截图
        if len(uia_text) < 50:
            return True
        # 如果只有窗口标题没有控件
        lines = uia_text.strip().split("\n")
        if len(lines) <= 1:
            return True
        return False

    def get_stats(self) -> dict:
        """获取优化统计"""
        return {
            "turns": self._turn_count,
            "estimated_saved_tokens": self._total_saved_tokens,
        }

    def reset(self):
        """重置状态（新任务开始时）"""
        self._last_uia_text = ""
        self._turn_count = 0
        self._total_saved_tokens = 0
