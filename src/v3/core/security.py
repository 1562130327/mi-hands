"""
SecurityManager - 安全层

职责：
1. 权限控制 - 危险操作需要确认
2. 沙箱隔离 - 限制操作范围
3. 操作日志 - 记录所有操作
4. 回滚机制 - 支持撤销操作

存储后端：操作日志和回滚栈统一使用 StateManager（SQLite）
"""

import json
import os
import time
from typing import Optional
from pathlib import Path
from datetime import datetime

from .state_manager import StateManager


class PermissionManager:
    """权限控制"""

    # 危险操作列表
    DANGEROUS_ACTIONS = [
        "delete_file", "execute_command", "modify_system",
        "send_network", "install_software", "format_disk"
    ]

    def __init__(self):
        self.auto_approve = False  # 是否自动批准危险操作

    def is_dangerous(self, action: str) -> bool:
        """检查操作是否危险"""
        return action in self.DANGEROUS_ACTIONS

    def check_permission(self, action: str, params: dict = None) -> bool:
        """
        检查操作权限

        Returns:
            True: 允许执行
            False: 需要确认或拒绝
        """
        if not self.is_dangerous(action):
            return True

        if self.auto_approve:
            return True

        # 危险操作需要确认
        return False

    def confirm_action(self, action: str, params: dict = None) -> bool:
        """
        确认危险操作

        根据 auto_approve 设置决定是否自动批准：
        - auto_approve=True: 自动批准（用于测试）
        - auto_approve=False: 需要人工确认（生产环境）

        Returns:
            True: 允许执行
            False: 拒绝执行
        """
        if self.auto_approve:
            print(f"WARNING: Auto-approved dangerous action '{action}'")
            return True

        # 需要人工确认
        print(f"WARNING: Dangerous action '{action}' requires confirmation")
        print(f"  Set auto_approve=True to auto-approve (for testing only)")
        return False


class SandboxManager:
    """沙箱隔离"""

    def __init__(self):
        self.allowed_paths = [
            str(Path.home()),
            "D:\\MI-Hands",
            "D:\\claude记忆",
        ]
        self.blocked_apps = [
            "format", "diskpart", "fdisk"
        ]
        self.max_actions_per_session = 1000
        self.action_count = 0

    def is_path_allowed(self, path: str) -> bool:
        """检查路径是否允许访问"""
        path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            if path.startswith(os.path.abspath(allowed)):
                return True
        return False

    def is_app_blocked(self, app: str) -> bool:
        """检查应用是否被阻止"""
        app_lower = app.lower()
        return any(blocked in app_lower for blocked in self.blocked_apps)

    def can_execute(self) -> bool:
        """检查是否可以继续执行"""
        return self.action_count < self.max_actions_per_session

    def record_action(self):
        """记录一次操作"""
        self.action_count += 1


class ActionLogger:
    """操作日志（SQLite 存储）"""

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()

    def log_action(self, action: str, params: dict, result: dict, duration: float):
        """
        记录一次操作

        Args:
            action: 操作类型
            params: 操作参数
            result: 执行结果
            duration: 执行时间（秒）
        """
        self.sm.add_log(
            action=action,
            params=params,
            result=result,
            duration=duration,
            success=result.get("success", False),
        )

    def get_history(self, limit: int = 100) -> list:
        """获取操作历史"""
        return self.sm.query_logs(limit=limit)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.sm.get_logs_stats()


class RollbackManager:
    """回滚机制（SQLite 存储）"""

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()
        self.max_stack_size = 50

    def save_state(self, action: str, state_data: dict):
        """
        保存当前状态（用于回滚）

        Args:
            action: 操作名称
            state_data: 状态数据
        """
        # 存到 logs 表，用 action 标记为 rollback
        self.sm.add_log(
            action=f"__rollback__:{action}",
            params={"action": action},
            result=state_data,
            success=True,
        )

    def rollback(self, steps: int = 1) -> Optional[list]:
        """
        回滚到之前的状态

        Args:
            steps: 回滚步数

        Returns:
            回滚的状态数据列表，失败返回 None
        """
        # 查找最近的 rollback 记录
        rollback_logs = self.sm.query_logs(
            action="__rollback__",
            limit=steps,
        )

        if not rollback_logs:
            print("No rollback data available")
            return None

        return rollback_logs

    def get_rollback_stack(self) -> list:
        """获取可回滚的操作列表"""
        return self.sm.query_logs(action="__rollback__", limit=self.max_stack_size)


class SecurityManager:
    """
    安全管理器 - 统一管理所有安全功能
    """

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()
        self.permissions = PermissionManager()
        self.sandbox = SandboxManager()
        self.logger = ActionLogger(state_manager=self.sm)
        self.rollback = RollbackManager(state_manager=self.sm)

    def check_and_log(self, action: str, params: dict = None) -> bool:
        """
        检查权限并记录操作

        Returns:
            True: 允许执行
            False: 拒绝执行
        """
        # 检查沙箱
        if not self.sandbox.can_execute():
            print("ERROR: Action limit reached for this session")
            return False

        # 检查权限
        if not self.permissions.check_permission(action, params):
            if not self.permissions.confirm_action(action, params):
                return False

        # 记录操作
        self.sandbox.record_action()

        return True

    def log_result(self, action: str, params: dict, result: dict, duration: float):
        """记录操作结果"""
        self.logger.log_action(action, params, result, duration)

    def get_history(self, limit: int = 100) -> list:
        """获取操作历史"""
        return self.logger.get_history(limit)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.logger.get_stats()
