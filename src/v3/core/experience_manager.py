"""
ExperienceManager - 操作经验管理（自进化系统核心）

与 MemoryManager / ReflectionManager 的区别：
- MemoryManager 侧重"记住了什么"（短期+长期记忆）
- ReflectionManager 侧重"学到了什么模式"（错误/成功模式分类）
- ExperienceManager 侧重"做过什么事、怎么做的"（完整的操作经验）

职责：
1. 记录成功经验 — 任务、步骤序列、最终结果
2. 记录失败经验 — 任务、失败步骤、失败原因、改进方向
3. 搜索相似任务的成功经验 — 按任务描述匹配，返回可复用的步骤
4. 学习和更新经验 — 合并重复经验、衰减过时经验、提炼最佳路径

存储后端：统一使用 StateManager（SQLite）
"""

import re
import hashlib
from typing import Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

from .state_manager import StateManager


# 经验库大小限制
MAX_EXPERIENCES = 1000
MAX_STEPS_PER_EXPERIENCE = 50

# 相似度阈值（低于这个分数不算"相似"）
SIMILARITY_THRESHOLD = 0.3


@dataclass
class StepRecord:
    """
    单个操作步骤记录

    记录每一步"做了什么、怎么做的、结果如何"，供后续复用时参考。
    """
    step_index: int                          # 步骤序号（从 0 开始）
    action_type: str                         # 动作类型（对应 ActionType 枚举值）
    params: dict = field(default_factory=dict)  # 动作参数
    target_control: str = ""                 # 目标控件
    description: str = ""                    # 步骤描述（给人看）
    duration_ms: float = 0.0                 # 耗时（毫秒）
    success: bool = True                     # 是否成功
    error_msg: str = ""                      # 失败时的错误信息
    screenshot_path: str = ""                # 执行后的截图路径（可选）
    retry_count: int = 0                     # 重试次数

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StepRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Experience:
    """
    一条完整的操作经验

    核心字段：
    - task: 用户的任务描述
    - steps: 执行的步骤序列（成功的或失败的）
    - success: 最终是否成功
    - tags: 标签（用于快速匹配）
    """
    exp_id: str                              # 唯一标识（时间戳 + 哈希）
    task: str                                # 任务描述
    steps: list[StepRecord] = field(default_factory=list)
    success: bool = True                     # 最终结果
    tags: list[str] = field(default_factory=list)   # 标签
    error_summary: str = ""                  # 失败原因摘要（仅失败经验）
    improvement: str = ""                    # 改进方向（仅失败经验）
    created_at: str = ""                     # 创建时间
    updated_at: str = ""                     # 最后更新时间
    use_count: int = 0                       # 被复用次数
    confidence: float = 1.0                  # 置信度（随时间衰减，复用成功则提升）
    app_context: str = ""                    # 目标应用（如 "Photoshop", "Chrome"）
    os_context: str = ""                     # 操作系统环境

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        data = asdict(self)
        data["steps"] = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Experience":
        steps_data = data.pop("steps", [])
        steps = [StepRecord.from_dict(s) for s in steps_data]
        return cls(steps=steps, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "steps"})


class ExperienceManager:
    """
    操作经验管理器（自进化系统核心）

    三层能力：
    1. 记录 — 任务完成后自动记录成功/失败经验
    2. 搜索 — 根据任务描述找到最相似的成功经验
    3. 学习 — 定期整理经验库，合并重复、衰减过时、提炼最佳路径
    """

    def __init__(self, state_manager: StateManager = None):
        """
        初始化经验管理器

        Args:
            state_manager: 共享的状态管理器实例（推荐传入，避免重复创建连接）
        """
        self.sm = state_manager or StateManager()
        self._experiences: dict[str, Experience] = {}
        self._index: dict[str, list[str]] = {}  # tag -> [exp_id, ...]
        self._load()

    # ============================================================
    # 持久化（从 SQLite 加载/保存）
    # ============================================================

    def _load(self):
        """从 SQLite 加载经验"""
        rows = self.sm.query_experiences(limit=MAX_EXPERIENCES)
        for row in rows:
            # 从 DB 格式转为 Experience 对象
            exp_dict = dict(row)
            exp_dict["steps"] = [
                StepRecord.from_dict(s) for s in (row.get("steps") or [])
            ]
            exp_id = exp_dict.pop("id", "")
            exp = Experience(exp_id=exp_id, **{
                k: v for k, v in exp_dict.items()
                if k in Experience.__dataclass_fields__
            })
            self._experiences[exp_id] = exp

        # 重建标签索引
        self._rebuild_index()

    def _save_experience(self, exp: Experience):
        """保存单条经验到 SQLite"""
        exp_data = exp.to_dict()
        exp_data["id"] = exp.exp_id
        self.sm.add_experience(exp_data)

    def _rebuild_index(self):
        """从经验数据重建标签索引"""
        self._index = {}
        for exp_id, exp in self._experiences.items():
            for tag in exp.tags:
                if tag not in self._index:
                    self._index[tag] = []
                if exp_id not in self._index[tag]:
                    self._index[tag].append(exp_id)

    # ============================================================
    # 记录经验
    # ============================================================

    def record_success(
        self,
        task: str,
        steps: list[dict],
        tags: list[str] = None,
        app_context: str = "",
    ) -> Experience:
        """
        记录一次成功经验

        Args:
            task: 任务描述（如 "打开 Photoshop 并新建画布"）
            steps: 步骤列表，每个元素是字典，包含 action_type, params 等
                   也支持 StepRecord 对象
            tags: 标签（如 ["photoshop", "新建", "画布"]）
            app_context: 目标应用

        Returns:
            创建的 Experience 对象
        """
        step_records = self._normalize_steps(steps)

        exp = Experience(
            exp_id=self._gen_id(task),
            task=task,
            steps=step_records,
            success=True,
            tags=tags or [],
            app_context=app_context,
        )

        self._add_experience(exp)
        return exp

    def record_failure(
        self,
        task: str,
        steps: list[dict],
        error_summary: str,
        improvement: str = "",
        tags: list[str] = None,
        app_context: str = "",
    ) -> Experience:
        """
        记录一次失败经验

        Args:
            task: 任务描述
            steps: 执行到失败时的步骤列表
            error_summary: 失败原因摘要
            improvement: 改进方向（可选，后续补充）
            tags: 标签
            app_context: 目标应用

        Returns:
            创建的 Experience 对象
        """
        step_records = self._normalize_steps(steps)

        exp = Experience(
            exp_id=self._gen_id(task),
            task=task,
            steps=step_records,
            success=False,
            tags=tags or [],
            error_summary=error_summary,
            improvement=improvement,
            app_context=app_context,
        )

        self._add_experience(exp)
        return exp

    def record_step_result(
        self,
        exp_id: str,
        step: dict,
    ) -> bool:
        """
        追加一个步骤到已有经验（边做边记录）

        Args:
            exp_id: 经验 ID
            step: 步骤数据

        Returns:
            是否追加成功
        """
        exp = self._experiences.get(exp_id)
        if not exp:
            return False

        step_record = StepRecord(
            step_index=len(exp.steps),
            action_type=step.get("action_type", ""),
            params=step.get("params", {}),
            target_control=step.get("target_control", ""),
            description=step.get("description", ""),
            duration_ms=step.get("duration_ms", 0.0),
            success=step.get("success", True),
            error_msg=step.get("error_msg", ""),
            retry_count=step.get("retry_count", 0),
        )

        if len(exp.steps) < MAX_STEPS_PER_EXPERIENCE:
            exp.steps.append(step_record)

        exp.updated_at = datetime.now().isoformat()
        self._save_experience(exp)
        return True

    def finalize_experience(
        self,
        exp_id: str,
        success: bool,
        error_summary: str = "",
        improvement: str = "",
    ) -> Optional[Experience]:
        """
        标记经验完成

        Args:
            exp_id: 经验 ID
            success: 最终是否成功
            error_summary: 失败原因
            improvement: 改进方向

        Returns:
            更新后的 Experience，如果 exp_id 不存在则返回 None
        """
        exp = self._experiences.get(exp_id)
        if not exp:
            return None

        exp.success = success
        exp.error_summary = error_summary
        exp.improvement = improvement
        exp.updated_at = datetime.now().isoformat()

        self._save_experience(exp)
        return exp

    # ============================================================
    # 搜索相似经验
    # ============================================================

    def search_similar(
        self,
        task: str,
        limit: int = 5,
        success_only: bool = False,
        app_context: str = "",
    ) -> list[Experience]:
        """
        搜索与当前任务相似的成功经验

        Args:
            task: 当前任务描述
            limit: 返回数量
            success_only: 是否只返回成功经验
            app_context: 当前应用上下文

        Returns:
            按相似度排序的经验列表
        """
        task_lower = task.lower()
        task_keywords = set(self._extract_keywords(task_lower))

        scored: list[tuple[float, Experience]] = []

        for exp in self._experiences.values():
            if success_only and not exp.success:
                continue
            if not exp.steps:
                continue

            score = self._calculate_similarity(
                task_keywords, task_lower, exp, app_context
            )

            if score >= SIMILARITY_THRESHOLD:
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def get_best_experience(
        self,
        task: str,
        app_context: str = "",
    ) -> Optional[Experience]:
        """获取一个最佳匹配经验"""
        results = self.search_similar(task, limit=1, success_only=True, app_context=app_context)
        if results:
            results[0].use_count += 1
            self._save_experience(results[0])
            return results[0]
        return None

    def get_failed_experience(
        self,
        task: str,
        app_context: str = "",
    ) -> Optional[Experience]:
        """查找类似任务的失败经验"""
        results = self.search_similar(task, limit=1, success_only=False, app_context=app_context)
        for exp in results:
            if not exp.success:
                return exp
        return None

    # ============================================================
    # 学习和更新
    # ============================================================

    def update_improvement(self, exp_id: str, improvement: str) -> bool:
        """为失败经验补充改进方向"""
        exp = self._experiences.get(exp_id)
        if not exp:
            return False

        exp.improvement = improvement
        exp.updated_at = datetime.now().isoformat()
        self._save_experience(exp)
        return True

    def boost_confidence(self, exp_id: str, amount: float = 0.1) -> float:
        """提升经验的置信度"""
        exp = self._experiences.get(exp_id)
        if not exp:
            return 0.0

        exp.confidence = min(1.0, exp.confidence + amount)
        exp.use_count += 1
        exp.updated_at = datetime.now().isoformat()
        self._save_experience(exp)
        return exp.confidence

    def decay_confidences(self, factor: float = 0.99):
        """全局衰减所有经验的置信度"""
        for exp in self._experiences.values():
            effective_factor = factor ** (1.0 / max(1, exp.use_count))
            exp.confidence *= effective_factor
            exp.confidence = max(0.01, exp.confidence)
            self._save_experience(exp)

    def merge_similar_experiences(self, threshold: float = 0.8) -> int:
        """合并高度相似的经验"""
        exp_list = list(self._experiences.values())
        merged_ids = set()
        merge_count = 0

        for i in range(len(exp_list)):
            if exp_list[i].exp_id in merged_ids:
                continue
            for j in range(i + 1, len(exp_list)):
                if exp_list[j].exp_id in merged_ids:
                    continue

                sim = self._direct_similarity(exp_list[i], exp_list[j])
                if sim >= threshold:
                    keep = exp_list[i] if exp_list[i].confidence >= exp_list[j].confidence else exp_list[j]
                    remove = exp_list[j] if keep == exp_list[i] else exp_list[i]

                    keep.use_count += remove.use_count
                    keep.tags = list(set(keep.tags + remove.tags))
                    keep.confidence = max(keep.confidence, remove.confidence)
                    keep.updated_at = datetime.now().isoformat()

                    merged_ids.add(remove.exp_id)
                    merge_count += 1

        for eid in merged_ids:
            del self._experiences[eid]
            self.sm.delete_experience(eid)

        if merge_count > 0:
            self._rebuild_index()

        return merge_count

    def remove_stale_experiences(self, min_confidence: float = 0.05) -> int:
        """清理陈旧经验"""
        stale_ids = [
            eid for eid, exp in self._experiences.items()
            if exp.confidence < min_confidence and exp.use_count == 0
        ]

        for eid in stale_ids:
            del self._experiences[eid]
            self.sm.delete_experience(eid)

        if stale_ids:
            self._rebuild_index()

        return len(stale_ids)

    def learn_from_task(
        self,
        task: str,
        steps: list[dict],
        success: bool,
        error_summary: str = "",
        improvement: str = "",
        tags: list[str] = None,
        app_context: str = "",
    ) -> Experience:
        """
        一步到位：记录经验 + 自动清理 + 返回经验

        Args:
            task: 任务描述
            steps: 步骤列表
            success: 是否成功
            error_summary: 失败原因
            improvement: 改进方向
            tags: 标签
            app_context: 目标应用

        Returns:
            创建的 Experience
        """
        if success:
            exp = self.record_success(task, steps, tags, app_context)
        else:
            exp = self.record_failure(task, steps, error_summary, improvement, tags, app_context)

        # 超过上限时自动清理
        if len(self._experiences) > MAX_EXPERIENCES:
            self.remove_stale_experiences()
            if len(self._experiences) > MAX_EXPERIENCES:
                self.merge_similar_experiences()

        return exp

    # ============================================================
    # 查询接口
    # ============================================================

    def get_experience(self, exp_id: str) -> Optional[Experience]:
        """根据 ID 获取经验"""
        return self._experiences.get(exp_id)

    def list_experiences(
        self,
        success_only: bool = None,
        app_context: str = "",
        tag: str = "",
        limit: int = 20,
    ) -> list[Experience]:
        """列出经验"""
        results = list(self._experiences.values())

        if success_only is not None:
            results = [e for e in results if e.success == success_only]
        if app_context:
            results = [e for e in results if e.app_context == app_context]
        if tag:
            results = [e for e in results if tag in e.tags]

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_experience_as_steps(self, exp_id: str) -> list[dict]:
        """获取经验的步骤列表（字典格式）"""
        exp = self._experiences.get(exp_id)
        if not exp:
            return []

        return [
            {
                "action_type": step.action_type,
                "params": step.params,
                "target_control": step.target_control,
                "description": step.description,
            }
            for step in exp.steps
        ]

    def get_task_advice(self, task: str, app_context: str = "") -> str:
        """根据历史经验为当前任务生成建议文本"""
        lines = []

        successes = self.search_similar(task, limit=2, success_only=True, app_context=app_context)
        for exp in successes:
            step_summary = " -> ".join(
                f"{s.action_type}({s.description or s.target_control})"
                for s in exp.steps[:5]
            )
            lines.append(
                f"- [成功经验] 任务: {exp.task}\n"
                f"  建议步骤: {step_summary}\n"
                f"  置信度: {exp.confidence:.0%}, 复用次数: {exp.use_count}"
            )

        failures = self.search_similar(task, limit=2, success_only=False, app_context=app_context)
        for exp in failures:
            if not exp.success:
                hint = exp.improvement or exp.error_summary
                lines.append(
                    f"- [失败教训] 任务: {exp.task}\n"
                    f"  失败原因: {exp.error_summary}\n"
                    f"  改进建议: {hint}"
                )

        if not lines:
            return ""

        return "\n".join([
            "## 操作经验参考（从历史学习）",
            *lines,
        ])

    def get_stats(self) -> dict:
        """获取经验库统计"""
        total = len(self._experiences)
        successes = sum(1 for e in self._experiences.values() if e.success)
        failures = total - successes

        avg_confidence = 0.0
        total_steps = 0
        if total > 0:
            avg_confidence = sum(e.confidence for e in self._experiences.values()) / total
            total_steps = sum(len(e.steps) for e in self._experiences.values())

        all_tags = set()
        for e in self._experiences.values():
            all_tags.update(e.tags)

        all_apps = set()
        for e in self._experiences.values():
            if e.app_context:
                all_apps.add(e.app_context)

        return {
            "total_experiences": total,
            "successes": successes,
            "failures": failures,
            "success_rate": f"{successes / total:.0%}" if total > 0 else "N/A",
            "total_steps": total_steps,
            "avg_confidence": round(avg_confidence, 3),
            "unique_tags": len(all_tags),
            "unique_apps": len(all_apps),
            "total_reuses": sum(e.use_count for e in self._experiences.values()),
        }

    # ============================================================
    # 内部工具方法
    # ============================================================

    def _add_experience(self, exp: Experience):
        """添加一条经验到库中"""
        self._experiences[exp.exp_id] = exp

        # 更新标签索引
        for tag in exp.tags:
            if tag not in self._index:
                self._index[tag] = []
            if exp.exp_id not in self._index[tag]:
                self._index[tag].append(exp.exp_id)

        # 写入 SQLite
        self._save_experience(exp)

        # 超过上限时自动清理
        if len(self._experiences) > MAX_EXPERIENCES:
            self.remove_stale_experiences()

    def _normalize_steps(self, steps: list) -> list[StepRecord]:
        """将各种格式的步骤统一转成 StepRecord"""
        records = []
        for i, step in enumerate(steps):
            if isinstance(step, StepRecord):
                step.step_index = i
                records.append(step)
            elif isinstance(step, dict):
                records.append(StepRecord(
                    step_index=i,
                    action_type=step.get("action_type", ""),
                    params=step.get("params", {}),
                    target_control=step.get("target_control", ""),
                    description=step.get("description", ""),
                    duration_ms=step.get("duration_ms", 0.0),
                    success=step.get("success", True),
                    error_msg=step.get("error_msg", ""),
                    retry_count=step.get("retry_count", 0),
                ))
        return records

    @staticmethod
    def _gen_id(task: str) -> str:
        """生成经验 ID（时间戳 + 任务哈希）"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        task_hash = hashlib.md5(task.encode()).hexdigest()[:8]
        return f"exp_{ts}_{task_hash}"

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """从文本中提取关键词（中英文混合）"""
        english_words = set(re.findall(r'[a-z]+', text.lower()))
        chinese_segments = set(re.findall(r'[一-鿿]+', text))
        keywords = english_words | chinese_segments
        return {k for k in keywords if len(k) >= 2}

    def _calculate_similarity(
        self,
        task_keywords: set[str],
        task_lower: str,
        exp: Experience,
        app_context: str,
    ) -> float:
        """计算任务与经验的相似度分数"""
        score = 0.0

        # 1. 关键词重叠度（40%）
        exp_keywords = set(self._extract_keywords(exp.task.lower()))
        if task_keywords and exp_keywords:
            overlap = len(task_keywords & exp_keywords)
            union = len(task_keywords | exp_keywords)
            if union > 0:
                score += 0.4 * (overlap / union)

        # 2. 文本包含关系（25%）
        exp_task_lower = exp.task.lower()
        if task_lower in exp_task_lower or exp_task_lower in task_lower:
            score += 0.25
        elif any(kw in exp_task_lower for kw in task_keywords if len(kw) >= 3):
            score += 0.15

        # 3. 标签匹配度（20%）
        if exp.tags:
            tag_overlap = sum(
                1 for tag in exp.tags
                if tag.lower() in task_lower or any(kw in tag.lower() for kw in task_keywords)
            )
            tag_score = tag_overlap / len(exp.tags)
            score += 0.2 * tag_score

        # 4. 应用上下文匹配（10%）
        if app_context and exp.app_context:
            if app_context.lower() == exp.app_context.lower():
                score += 0.1

        # 5. 置信度加权（5%）
        score += 0.05 * exp.confidence

        return score

    def _direct_similarity(self, exp_a: Experience, exp_b: Experience) -> float:
        """直接比较两条经验的相似度"""
        task_a = set(self._extract_keywords(exp_a.task.lower()))
        task_b = set(self._extract_keywords(exp_b.task.lower()))

        if not task_a or not task_b:
            return 0.0

        overlap = len(task_a & task_b)
        union = len(task_a | task_b)

        if union == 0:
            return 0.0

        text_sim = overlap / union

        if exp_a.success == exp_b.success:
            text_sim += 0.1
        if exp_a.app_context and exp_a.app_context == exp_b.app_context:
            text_sim += 0.05

        if exp_a.steps and exp_b.steps:
            types_a = [s.action_type for s in exp_a.steps]
            types_b = [s.action_type for s in exp_b.steps]
            step_sim = self._sequence_similarity(types_a, types_b)
            text_sim = text_sim * 0.6 + step_sim * 0.4

        return min(1.0, text_sim)

    @staticmethod
    def _sequence_similarity(seq_a: list, seq_b: list) -> float:
        """计算两个序列的相似度（基于最长公共子序列比例）"""
        if not seq_a or not seq_b:
            return 0.0

        m, n = len(seq_a), len(seq_b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq_a[i - 1] == seq_b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_len = dp[m][n]
        return lcs_len / max(m, n)
