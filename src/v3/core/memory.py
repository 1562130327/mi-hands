"""
MemoryManager - 记忆系统

职责：
1. 短期记忆 - 当前会话的操作历史
2. 长期记忆 - 持久化的学习记录
3. 工作记忆 - 当前任务的上下文

存储后端：统一使用 StateManager（SQLite）
"""

import json
from typing import Optional
from datetime import datetime

from .state_manager import StateManager


class MemoryManager:
    """
    记忆系统

    三层记忆架构：
    - 短期记忆：当前会话，会话结束就丢失
    - 长期记忆：持久化存储，跨会话保留
    - 工作记忆：当前任务的上下文（内存中）
    """

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()

        self.short_term = []        # 短期记忆（当前会话，同时写入 DB）
        self.working = {}           # 工作记忆（当前任务，仅内存）

        # 启动时从 DB 加载最近的短期记忆
        self._load_short_term()

    def _load_short_term(self):
        """从 DB 加载最近的短期记忆"""
        rows = self.sm.query_memories(memory_type="short", limit=100)
        self.short_term = rows

    # ============================================================
    # 短期记忆
    # ============================================================

    def remember_short(self, action: str, result: dict, context: dict = None):
        """
        记住一次操作（短期记忆）

        Args:
            action: 操作类型
            result: 执行结果
            context: 上下文信息
        """
        entry = {
            "action": action,
            "result": result,
            "context": context or {},
        }

        # 写入 SQLite
        memory_id = self.sm.add_memory(
            memory_data=entry,
            memory_type="short",
            action=action,
        )

        # 内存列表也同步
        entry["id"] = memory_id
        entry["timestamp"] = datetime.now().isoformat()
        self.short_term.append(entry)

        # 限制内存列表大小
        if len(self.short_term) > 100:
            self.short_term = self.short_term[-100:]

        # 同时清理 DB 中的旧短期记忆
        self.sm.clean_old_memories(memory_type="short", max_count=100)

    def recall_short(self, action: str = None, limit: int = 10) -> list:
        """
        回忆短期记忆

        Args:
            action: 过滤操作类型
            limit: 返回数量

        Returns:
            匹配的记忆列表
        """
        if action:
            return self.sm.query_memories(memory_type="short", action=action, limit=limit)

        # 从内存获取（更快）
        memories = self.short_term
        return memories[-limit:]

    # ============================================================
    # 长期记忆
    # ============================================================

    def remember_long(self, category: str, data: dict):
        """
        记住一条长期记忆

        Args:
            category: 分类（tasks/errors/successes/learned_skills）
            data: 数据
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        self.sm.add_memory(
            memory_data=entry,
            memory_type="long",
            category=category,
        )

    def recall_long(self, category: str, keyword: str = None, limit: int = 10) -> list:
        """
        回忆长期记忆

        Args:
            category: 分类
            keyword: 关键词过滤
            limit: 返回数量

        Returns:
            匹配的记忆列表
        """
        return self.sm.query_memories(
            memory_type="long",
            category=category,
            keyword=keyword,
            limit=limit,
        )

    # ============================================================
    # 工作记忆（纯内存，不需要持久化）
    # ============================================================

    def set_working(self, key: str, value):
        """设置工作记忆"""
        self.working[key] = value

    def get_working(self, key: str, default=None):
        """获取工作记忆"""
        return self.working.get(key, default)

    def clear_working(self):
        """清空工作记忆"""
        self.working = {}

    # ============================================================
    # 便捷方法
    # ============================================================

    def remember_task(self, task: str, result: dict, success: bool):
        """记住一次任务执行"""
        data = {
            "task": task,
            "success": success,
            "result_summary": result.get("message", "")[:200],
        }

        self.remember_short("task", data)
        self.remember_long("successes" if success else "errors", data)

    def remember_error(self, action: str, error: str, context: dict = None):
        """记住一次错误"""
        data = {
            "action": action,
            "error": error,
            "context": context or {},
        }

        self.remember_short("error", data)
        self.remember_long("errors", data)

    def recall_similar_tasks(self, task: str, limit: int = 5) -> list:
        """
        回忆类似任务的历史

        Args:
            task: 当前任务描述
            limit: 返回数量

        Returns:
            类似任务的历史记录
        """
        # 搜索成功和失败记录
        successes = self.recall_long("successes", task, limit)
        errors = self.recall_long("errors", task, limit)

        # 合并并按时间排序
        all_memories = successes + errors
        all_memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return all_memories[:limit]

    def get_stats(self) -> dict:
        """获取记忆统计"""
        return {
            "short_term_count": len(self.short_term),
            "long_term_total": self.sm.count_memories(memory_type="long"),
            "working_memory_keys": list(self.working.keys()),
        }
