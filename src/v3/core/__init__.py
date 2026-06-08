"""
核心引擎 - 三层架构 + 完整模块

三层分工：
1. HostAgent (决策层) - 理解任务，规划步骤
2. AppAgent (执行层) - 执行具体操作
3. VerifyLayer (验证层) - 检查结果

完整模块：
4. SecurityManager (安全层) - 权限/沙箱/日志/回滚
5. MemoryManager (记忆系统) - 操作历史/学习记录
6. ReflectionManager (反思学习) - 从错误中改进
7. ScriptExecutor (脚本执行) - 安全执行代码
8. FileOperations (文件操作) - 读写文件
9. MetricsCollector (性能监控) - 指标收集
10. SkillManager (技能管理) - 自动学习新能力
11. ContinuousAwareness (持续感知) - 借鉴 cellar Cortex
12. EntityResolver (实体操作) - 借鉴 desktop-touch
13. PhysicalHID (物理 HID) - 借鉴 clawtouch
14. ExperienceManager (操作经验) - 自进化系统核心，记录/搜索/学习操作经验
15. LearningLoop (学习循环) - 闭环反馈：规划 → 执行 → 验证 → 反馈 → 再规划
"""

from .state_manager import StateManager
from .host_agent import HostAgent
from .app_agent import AppAgent
from .verify import VerifyLayer
from .action_models import Action, TaskPlan, ActionType
from .security import SecurityManager
from .memory import MemoryManager
from .reflection import ReflectionManager
from .script_executor import ScriptExecutor
from .file_ops import FileOperations
from .metrics import MetricsCollector
from .skill_manager import SkillManager
from .continuous_awareness import ContinuousAwareness
from .entity_operations import EntityResolver, EntityType, Entity
from .physical_hid import PhysicalHID, HIDMethod
from .experience_manager import ExperienceManager, Experience, StepRecord
from .learning_loop import LearningLoop, LoopState, VerificationResult, FeedbackReport

__all__ = [
    # 统一状态管理
    "StateManager",
    # 三层架构
    "HostAgent",
    "AppAgent",
    "VerifyLayer",
    "Action",
    "TaskPlan",
    "ActionType",
    # 完整模块
    "SecurityManager",
    "MemoryManager",
    "ReflectionManager",
    "ScriptExecutor",
    "FileOperations",
    "MetricsCollector",
    "SkillManager",
    # 新增：借鉴其他 MCP 的设计理念
    "ContinuousAwareness",  # 借鉴 cellar
    "EntityResolver",       # 借鉴 desktop-touch
    "EntityType",
    "Entity",
    "PhysicalHID",          # 借鉴 clawtouch
    "HIDMethod",
    # 自进化系统
    "ExperienceManager",    # 操作经验管理
    "Experience",
    "StepRecord",
    # 学习循环
    "LearningLoop",         # 闭环反馈系统
    "LoopState",
    "VerificationResult",
    "FeedbackReport",
]
