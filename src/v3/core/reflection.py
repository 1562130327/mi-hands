"""
ReflectionManager - 反思学习

职责：
1. 记录错误模式
2. 记录成功模式
3. 从错误中学习
4. 改进决策 prompt

存储后端：统一使用 StateManager（SQLite）
"""

from typing import Optional
from datetime import datetime

from .state_manager import StateManager


class ReflectionManager:
    """
    反思学习系统

    从成功和失败中学习，改进建议：
    - 记录错误模式和修复方案
    - 记录成功模式和最佳实践
    - 根据历史改进建议
    """

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()

    # ============================================================
    # 错误学习
    # ============================================================

    def record_error(self, action: str, error: str, context: dict = None, fix: str = None):
        """
        记录一次错误

        Args:
            action: 操作类型
            error: 错误信息
            context: 上下文
            fix: 修复方案（如果有）
        """
        error_type = self._classify_error(error)

        # 获取现有模式
        existing = self.sm.get_pattern("error", error_type)

        examples = existing.get("examples", []) if existing else []
        examples.append({
            "action": action,
            "error": error[:200],
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        })

        # 限制示例数量
        if len(examples) > 10:
            examples = examples[-10:]

        fixes = existing.get("fixes", []) if existing else []
        if fix and fix not in fixes:
            fixes.append(fix)

        self.sm.upsert_pattern(
            pattern_type="error",
            pattern_key=error_type,
            count=1,
            examples=examples,
            fixes=fixes,
        )

    def _classify_error(self, error: str) -> str:
        """错误分类"""
        error_lower = error.lower()

        if "timeout" in error_lower or "timed out" in error_lower:
            return "timeout"
        elif "permission" in error_lower or "access denied" in error_lower:
            return "permission"
        elif "not found" in error_lower or "no such file" in error_lower:
            return "not_found"
        elif "connection" in error_lower or "network" in error_lower:
            return "network"
        elif "api" in error_lower or "token" in error_lower:
            return "api_error"
        elif "ui" in error_lower or "element" in error_lower:
            return "ui_error"
        else:
            return "other"

    def suggest_fix(self, error_type: str) -> Optional[str]:
        """
        根据错误类型建议修复方案

        Args:
            error_type: 错误类型

        Returns:
            修复建议，没有则返回 None
        """
        pattern = self.sm.get_pattern("error", error_type)
        if not pattern:
            return None

        # 返回最常见的修复方案
        fixes = pattern.get("fixes", [])
        if fixes:
            return fixes[0]

        # 根据错误类型返回通用建议
        suggestions = {
            "timeout": "增加等待时间，或简化操作步骤",
            "permission": "检查文件权限，或以管理员身份运行",
            "not_found": "检查路径是否正确，或搜索相关文件",
            "network": "检查网络连接，或使用代理",
            "api_error": "检查 API Key 配额，或稍后重试",
            "ui_error": "等待 UI 加载完成，或刷新界面",
        }

        return suggestions.get(error_type)

    # ============================================================
    # 成功学习
    # ============================================================

    def record_success(self, action: str, result: dict, context: dict = None):
        """
        记录一次成功

        Args:
            action: 操作类型
            result: 执行结果
            context: 上下文
        """
        success_type = self._classify_success(action, result)

        existing = self.sm.get_pattern("success", success_type)

        examples = existing.get("examples", []) if existing else []
        examples.append({
            "action": action,
            "result_summary": str(result)[:200],
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        })

        # 限制示例数量
        if len(examples) > 10:
            examples = examples[-10:]

        self.sm.upsert_pattern(
            pattern_type="success",
            pattern_key=success_type,
            count=1,
            examples=examples,
        )

    def _classify_success(self, action: str, result: dict) -> str:
        """成功分类"""
        if "draw" in action.lower():
            return "drawing"
        elif "click" in action.lower():
            return "clicking"
        elif "type" in action.lower():
            return "typing"
        elif "file" in action.lower():
            return "file_ops"
        else:
            return "general"

    def add_best_practice(self, success_type: str, practice: str):
        """添加最佳实践"""
        existing = self.sm.get_pattern("success", success_type)
        practices = existing.get("best_practices", []) if existing else []

        if practice not in practices:
            practices.append(practice)
            self.sm.upsert_pattern(
                pattern_type="success",
                pattern_key=success_type,
                count=existing.get("count", 0) if existing else 0,
                best_practices=practices,
            )

    # ============================================================
    # 改进建议
    # ============================================================

    def add_improvement(self, suggestion: str):
        """添加改进建议"""
        self.sm.add_improvement(suggestion)

    def get_improvements(self, unimplemented_only: bool = True) -> list:
        """获取改进建议"""
        return self.sm.get_improvements(unimplemented_only=unimplemented_only)

    # ============================================================
    # 改进 Prompt
    # ============================================================

    def get_improved_prompt(self, task: str) -> str:
        """
        根据学习结果生成改进建议

        Args:
            task: 用户任务

        Returns:
            改进建议文本
        """
        suggestions = []

        # 检查错误模式（出现多次的才提醒）
        error_patterns = self.sm.query_patterns(pattern_type="error")
        for p in error_patterns:
            if p.get("count", 0) > 2:
                fix = self.suggest_fix(p["pattern_key"])
                if fix:
                    suggestions.append(f"避免错误 [{p['pattern_key']}]: {fix}")

        # 检查成功模式
        success_patterns = self.sm.query_patterns(pattern_type="success")
        for p in success_patterns:
            practices = p.get("best_practices", [])
            if practices:
                suggestions.append(f"最佳实践 [{p['pattern_key']}]: {practices[0]}")

        if not suggestions:
            return ""

        return "\n".join([
            "## 经验教训（从历史学习）",
            *[f"- {s}" for s in suggestions]
        ])

    def get_stats(self) -> dict:
        """获取学习统计"""
        all_patterns = self.sm.query_patterns()
        error_count = sum(1 for p in all_patterns if p.get("pattern_type") == "error")
        success_count = sum(1 for p in all_patterns if p.get("pattern_type") == "success")
        total_errors = sum(p.get("count", 0) for p in all_patterns if p.get("pattern_type") == "error")
        total_successes = sum(p.get("count", 0) for p in all_patterns if p.get("pattern_type") == "success")

        return {
            "error_patterns_count": error_count,
            "success_patterns_count": success_count,
            "improvements_count": len(self.sm.get_improvements(unimplemented_only=False)),
            "total_errors": total_errors,
            "total_successes": total_successes,
        }
