"""
MetricsCollector - 性能监控

职责：
1. 收集操作指标
2. 计算统计数据
3. 生成报告

存储后端：统一使用 StateManager（SQLite）
"""

from typing import Optional

from .state_manager import StateManager


class MetricsCollector:
    """
    性能指标收集器

    收集和分析操作性能：
    - 操作次数
    - 成功率
    - 响应时间
    - 错误分布
    """

    def __init__(self, state_manager: StateManager = None):
        self.sm = state_manager or StateManager()

    def record_action(self, action_type: str, duration: float, success: bool, error_type: str = None):
        """
        记录一次操作

        Args:
            action_type: 操作类型
            duration: 执行时间（秒）
            success: 是否成功
            error_type: 错误类型（失败时）
        """
        self.sm.add_metric(
            action_type=action_type,
            duration=duration,
            success=success,
            error_type=error_type or "",
        )

        # 定期清理旧数据
        self.sm.clean_old_metrics(max_count=1000)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.sm.get_metrics_stats()

    def get_avg_response_time(self, action_type: str = None) -> float:
        """
        获取平均响应时间

        Args:
            action_type: 过滤操作类型

        Returns:
            平均响应时间（秒）
        """
        stats = self.sm.get_metrics_stats(action_type=action_type)
        return stats.get("avg_duration", 0.0)

    def get_success_rate(self, action_type: str = None) -> float:
        """
        获取成功率

        Args:
            action_type: 过滤操作类型

        Returns:
            成功率 (0-1)
        """
        stats = self.sm.get_metrics_stats(action_type=action_type)
        return stats.get("success_rate", 0.0)

    def get_action_distribution(self) -> dict:
        """获取操作类型分布"""
        return self.sm.get_action_distribution()

    def get_error_distribution(self) -> dict:
        """获取错误类型分布"""
        return self.sm.get_error_distribution()

    def get_recent_actions(self, limit: int = 10) -> list:
        """获取最近的操作"""
        return self.sm.query_metrics(limit=limit)

    def export_report(self) -> str:
        """导出报告"""
        stats = self.get_stats()
        distribution = self.get_action_distribution()
        errors = self.get_error_distribution()

        report = [
            "=" * 50,
            "MI Hands Performance Report",
            "=" * 50,
            "",
            "Overall Stats:",
            f"  Total Actions: {stats.get('total_actions', 0)}",
            f"  Success: {stats.get('success_count', 0)} ({stats.get('success_rate', 0):.1%})",
            f"  Errors: {stats.get('error_count', 0)} ({1 - stats.get('success_rate', 0):.1%})",
            f"  Avg Response Time: {stats.get('avg_duration', 0):.2f}s",
            "",
            "Action Distribution:",
        ]

        for action_type, data in sorted(distribution.items(), key=lambda x: x[1]['count'], reverse=True):
            report.append(f"  {action_type}: {data['count']} ({data['percentage']:.1f}%)")

        if errors:
            report.append("")
            report.append("Error Distribution:")
            for error_type, data in sorted(errors.items(), key=lambda x: x[1]['count'], reverse=True):
                report.append(f"  {error_type}: {data['count']} ({data['percentage']:.1f}%)")

        return "\n".join(report)

    def reset(self):
        """重置指标（删除所有指标数据）"""
        # 直接清理所有指标
        self.sm.clean_old_metrics(max_count=0)
