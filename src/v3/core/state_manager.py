"""
StateManager - 统一状态管理（SQLite）

把分散的 JSON 状态文件统一到一个 SQLite 数据库：
- experiences: 经验记录（来自 experience_manager.py）
- memories: 记忆数据（来自 memory.py）
- metrics: 性能指标（来自 metrics.py）
- logs: 操作日志（来自 security.py）
- patterns: 学习模式（来自 reflection.py）

好处：
1. 原子性写入 — 不会写到一半崩了导致数据损坏
2. 并发安全 — SQLite 内置锁
3. 高效查询 — 支持索引、聚合、过滤
4. 单文件存储 — 所有状态在 state/mi_hands.db 里
5. 事务支持 — 批量操作可以回滚

用法：
    sm = StateManager()
    sm.add_memory({"action": "click", "result": "ok"})
    memories = sm.query_memories(action="click")
"""

import json
import sqlite3
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager


# 数据库文件路径
STATE_DIR = Path(__file__).parent.parent.parent.parent / "state"
DB_PATH = STATE_DIR / "mi_hands.db"


class StateManager:
    """
    统一状态管理器 — SQLite 后端

    所有模块共享同一个数据库，通过表名区分数据类型。
    支持完整的 CRUD 操作和灵活的查询/统计。
    """

    def __init__(self, db_path: str = None):
        """
        初始化状态管理器

        Args:
            db_path: 数据库文件路径，默认为 state/mi_hands.db
        """
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = None
        self._connect()
        self._init_tables()

    # ============================================================
    # 连接管理
    # ============================================================

    def _connect(self):
        """建立数据库连接"""
        self._conn = sqlite3.connect(
            str(self._db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        # 开启 WAL 模式提升并发性能
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @contextmanager
    def _transaction(self):
        """事务上下文管理器 — 自动提交/回滚"""
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ============================================================
    # 建表
    # ============================================================

    def _init_tables(self):
        """初始化所有表结构"""
        with self._transaction() as cur:
            # 经验记录表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    steps_json TEXT DEFAULT '[]',
                    success INTEGER DEFAULT 1,
                    tags_json TEXT DEFAULT '[]',
                    error_summary TEXT DEFAULT '',
                    improvement TEXT DEFAULT '',
                    app_context TEXT DEFAULT '',
                    os_context TEXT DEFAULT '',
                    use_count INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 记忆数据表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    action TEXT DEFAULT '',
                    data_json TEXT NOT NULL,
                    context_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)

            # 性能指标表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    duration REAL DEFAULT 0.0,
                    success INTEGER DEFAULT 1,
                    error_type TEXT DEFAULT '',
                    timestamp TEXT NOT NULL
                )
            """)

            # 操作日志表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    params_json TEXT DEFAULT '{}',
                    result_json TEXT DEFAULT '{}',
                    duration REAL DEFAULT 0.0,
                    success INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)

            # 学习模式表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_key TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    examples_json TEXT DEFAULT '[]',
                    fixes_json TEXT DEFAULT '[]',
                    best_practices_json TEXT DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    UNIQUE(pattern_type, pattern_key)
                )
            """)

            # 改进建议表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suggestion TEXT NOT NULL,
                    implemented INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # 数据迁移记录表（防止重复迁移）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    migrated_at TEXT NOT NULL
                )
            """)

            # 建索引加速查询
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memories_action ON memories(action)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(action_type)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)")

    # ============================================================
    # 经验记录 CRUD
    # ============================================================

    def add_experience(self, exp_data: dict) -> str:
        """
        添加一条经验

        Args:
            exp_data: 经验字典，必须包含 id, task, created_at, updated_at

        Returns:
            经验 ID
        """
        with self._transaction() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO experiences
                (id, task, steps_json, success, tags_json, error_summary,
                 improvement, app_context, os_context, use_count,
                 confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp_data["id"],
                exp_data["task"],
                json.dumps(exp_data.get("steps", []), ensure_ascii=False),
                1 if exp_data.get("success", True) else 0,
                json.dumps(exp_data.get("tags", []), ensure_ascii=False),
                exp_data.get("error_summary", ""),
                exp_data.get("improvement", ""),
                exp_data.get("app_context", ""),
                exp_data.get("os_context", ""),
                exp_data.get("use_count", 0),
                exp_data.get("confidence", 1.0),
                exp_data["created_at"],
                exp_data["updated_at"],
            ))
        return exp_data["id"]

    def get_experience(self, exp_id: str) -> Optional[dict]:
        """根据 ID 获取经验"""
        row = self._conn.execute(
            "SELECT * FROM experiences WHERE id = ?", (exp_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def update_experience(self, exp_id: str, updates: dict) -> bool:
        """
        更新经验字段

        Args:
            exp_id: 经验 ID
            updates: 要更新的字段字典

        Returns:
            是否更新成功
        """
        allowed = {
            "task", "steps_json", "success", "tags_json", "error_summary",
            "improvement", "app_context", "os_context", "use_count",
            "confidence", "updated_at",
        }
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False

        # JSON 字段自动序列化
        if "steps_json" in fields and isinstance(fields["steps_json"], list):
            fields["steps_json"] = json.dumps(fields["steps_json"], ensure_ascii=False)
        if "tags_json" in fields and isinstance(fields["tags_json"], list):
            fields["tags_json"] = json.dumps(fields["tags_json"], ensure_ascii=False)
        if "success" in fields:
            fields["success"] = 1 if fields["success"] else 0

        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [exp_id]

        with self._transaction() as cur:
            cur.execute(f"UPDATE experiences SET {set_clause} WHERE id = ?", values)
            return cur.rowcount > 0

    def delete_experience(self, exp_id: str) -> bool:
        """删除一条经验"""
        with self._transaction() as cur:
            cur.execute("DELETE FROM experiences WHERE id = ?", (exp_id,))
            return cur.rowcount > 0

    def query_experiences(
        self,
        success_only: bool = None,
        app_context: str = "",
        tag: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """
        查询经验列表

        Args:
            success_only: True=只看成功的，False=只看失败的，None=全部
            app_context: 按应用过滤
            tag: 按标签过滤（JSON 数组包含）
            limit: 返回数量
            offset: 偏移量（分页用）

        Returns:
            经验字典列表
        """
        conditions = []
        params = []

        if success_only is not None:
            conditions.append("success = ?")
            params.append(1 if success_only else 0)

        if app_context:
            conditions.append("app_context = ?")
            params.append(app_context)

        if tag:
            conditions.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM experiences {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_experiences(self, success_only: bool = None) -> int:
        """统计经验数量"""
        if success_only is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM experiences WHERE success = ?",
                (1 if success_only else 0,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()
        return row[0] if row else 0

    # ============================================================
    # 记忆数据 CRUD
    # ============================================================

    def add_memory(self, memory_data: dict, memory_type: str = "short",
                   category: str = "", action: str = "") -> int:
        """
        添加一条记忆

        Args:
            memory_data: 记忆数据字典
            memory_type: 记忆类型（short/long/working）
            category: 分类（长期记忆用）
            action: 操作类型

        Returns:
            记忆 ID
        """
        with self._transaction() as cur:
            cur.execute("""
                INSERT INTO memories (memory_type, category, action, data_json, context_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                memory_type,
                category,
                action,
                json.dumps(memory_data, ensure_ascii=False),
                json.dumps(memory_data.get("context", {}), ensure_ascii=False),
                datetime.now().isoformat(),
            ))
            return cur.lastrowid

    def get_memory(self, memory_id: int) -> Optional[dict]:
        """根据 ID 获取记忆"""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_memory(self, memory_id: int) -> bool:
        """删除一条记忆"""
        with self._transaction() as cur:
            cur.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def query_memories(
        self,
        memory_type: str = None,
        category: str = None,
        action: str = None,
        keyword: str = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict]:
        """
        查询记忆列表

        Args:
            memory_type: 按记忆类型过滤
            category: 按分类过滤
            action: 按操作类型过滤
            keyword: 关键词搜索（在 data_json 中匹配）
            limit: 返回数量
            offset: 偏移量

        Returns:
            记忆字典列表
        """
        conditions = []
        params = []

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if keyword:
            conditions.append("data_json LIKE ?")
            params.append(f"%{keyword}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM memories {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_memories(self, memory_type: str = None) -> int:
        """统计记忆数量"""
        if memory_type:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (memory_type,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0] if row else 0

    def clean_old_memories(self, memory_type: str = "short", max_count: int = 100) -> int:
        """
        清理旧的短期记忆（保留最新的 max_count 条）

        Returns:
            删除的记忆数量
        """
        with self._transaction() as cur:
            # 找到保留边界
            rows = cur.execute(
                "SELECT id FROM memories WHERE memory_type = ? ORDER BY created_at DESC LIMIT 1 OFFSET ?",
                (memory_type, max_count - 1)
            ).fetchall()

            if not rows:
                return 0

            cutoff_id = rows[0]["id"]
            cur.execute(
                "DELETE FROM memories WHERE memory_type = ? AND id < ?",
                (memory_type, cutoff_id)
            )
            return cur.rowcount

    # ============================================================
    # 性能指标 CRUD
    # ============================================================

    def add_metric(self, action_type: str, duration: float, success: bool,
                   error_type: str = "") -> int:
        """
        添加一条性能指标

        Args:
            action_type: 操作类型
            duration: 执行时间（秒）
            success: 是否成功
            error_type: 错误类型

        Returns:
            指标 ID
        """
        with self._transaction() as cur:
            cur.execute("""
                INSERT INTO metrics (action_type, duration, success, error_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                action_type,
                duration,
                1 if success else 0,
                error_type,
                datetime.now().isoformat(),
            ))
            return cur.lastrowid

    def get_metric(self, metric_id: int) -> Optional[dict]:
        """根据 ID 获取指标"""
        row = self._conn.execute(
            "SELECT * FROM metrics WHERE id = ?", (metric_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_metric(self, metric_id: int) -> bool:
        """删除一条指标"""
        with self._transaction() as cur:
            cur.execute("DELETE FROM metrics WHERE id = ?", (metric_id,))
            return cur.rowcount > 0

    def query_metrics(
        self,
        action_type: str = None,
        success_only: bool = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        查询指标列表

        Args:
            action_type: 按操作类型过滤
            success_only: 是否只查成功/失败的
            limit: 返回数量
            offset: 偏移量

        Returns:
            指标字典列表
        """
        conditions = []
        params = []

        if action_type:
            conditions.append("action_type = ?")
            params.append(action_type)
        if success_only is not None:
            conditions.append("success = ?")
            params.append(1 if success_only else 0)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM metrics {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_metrics_stats(self, action_type: str = None) -> dict:
        """
        获取性能统计

        Returns:
            包含 total, success, error, avg_duration 的统计字典
        """
        where = ""
        params = []
        if action_type:
            where = "WHERE action_type = ?"
            params = [action_type]

        row = self._conn.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
                AVG(duration) as avg_duration,
                MIN(duration) as min_duration,
                MAX(duration) as max_duration
            FROM metrics {where}
        """, params).fetchone()

        if not row:
            return {}

        total = row["total"]
        success = row["success_count"] or 0
        return {
            "total_actions": total,
            "success_count": success,
            "error_count": row["error_count"] or 0,
            "success_rate": success / total if total > 0 else 0,
            "avg_duration": round(row["avg_duration"] or 0, 3),
            "min_duration": round(row["min_duration"] or 0, 3),
            "max_duration": round(row["max_duration"] or 0, 3),
        }

    def get_action_distribution(self) -> dict:
        """获取操作类型分布"""
        rows = self._conn.execute("""
            SELECT action_type, COUNT(*) as cnt
            FROM metrics
            GROUP BY action_type
            ORDER BY cnt DESC
        """).fetchall()

        total = sum(r["cnt"] for r in rows)
        return {
            r["action_type"]: {
                "count": r["cnt"],
                "percentage": r["cnt"] / total * 100 if total > 0 else 0,
            }
            for r in rows
        }

    def get_error_distribution(self) -> dict:
        """获取错误类型分布"""
        rows = self._conn.execute("""
            SELECT error_type, COUNT(*) as cnt
            FROM metrics
            WHERE success = 0 AND error_type != ''
            GROUP BY error_type
            ORDER BY cnt DESC
        """).fetchall()

        total = sum(r["cnt"] for r in rows)
        return {
            r["error_type"]: {
                "count": r["cnt"],
                "percentage": r["cnt"] / total * 100 if total > 0 else 0,
            }
            for r in rows
        }

    def clean_old_metrics(self, max_count: int = 1000) -> int:
        """清理旧的性能指标"""
        with self._transaction() as cur:
            rows = cur.execute(
                "SELECT id FROM metrics ORDER BY timestamp DESC LIMIT 1 OFFSET ?",
                (max_count - 1,)
            ).fetchall()
            if not rows:
                return 0
            cutoff_id = rows[0]["id"]
            cur.execute("DELETE FROM metrics WHERE id < ?", (cutoff_id,))
            return cur.rowcount

    # ============================================================
    # 操作日志 CRUD
    # ============================================================

    def add_log(self, action: str, params: dict = None, result: dict = None,
                duration: float = 0.0, success: bool = False) -> int:
        """
        添加一条操作日志

        Args:
            action: 操作类型
            params: 操作参数
            result: 执行结果
            duration: 执行时间（秒）
            success: 是否成功

        Returns:
            日志 ID
        """
        with self._transaction() as cur:
            cur.execute("""
                INSERT INTO logs (action, params_json, result_json, duration, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                action,
                json.dumps(params or {}, ensure_ascii=False),
                json.dumps(result or {}, ensure_ascii=False),
                duration,
                1 if success else 0,
                datetime.now().isoformat(),
            ))
            return cur.lastrowid

    def get_log(self, log_id: int) -> Optional[dict]:
        """根据 ID 获取日志"""
        row = self._conn.execute(
            "SELECT * FROM logs WHERE id = ?", (log_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_log(self, log_id: int) -> bool:
        """删除一条日志"""
        with self._transaction() as cur:
            cur.execute("DELETE FROM logs WHERE id = ?", (log_id,))
            return cur.rowcount > 0

    def query_logs(
        self,
        action: str = None,
        success_only: bool = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        查询操作日志

        Args:
            action: 按操作类型过滤
            success_only: 是否只查成功/失败的
            limit: 返回数量
            offset: 偏移量

        Returns:
            日志字典列表
        """
        conditions = []
        params = []

        if action:
            conditions.append("action = ?")
            params.append(action)
        if success_only is not None:
            conditions.append("success = ?")
            params.append(1 if success_only else 0)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_logs_stats(self) -> dict:
        """获取日志统计"""
        row = self._conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
            FROM logs
        """).fetchone()

        if not row:
            return {}

        total = row["total"]
        success = row["success_count"] or 0
        return {
            "total": total,
            "success": success,
            "error": row["error_count"] or 0,
            "success_rate": success / total if total > 0 else 0,
        }

    # ============================================================
    # 学习模式 CRUD
    # ============================================================

    def upsert_pattern(self, pattern_type: str, pattern_key: str,
                       count: int = 1, examples: list = None,
                       fixes: list = None, best_practices: list = None) -> int:
        """
        插入或更新学习模式

        Args:
            pattern_type: 模式类型（error_pattern / success_pattern）
            pattern_key: 模式键名（如 "timeout", "clicking"）
            count: 出现次数
            examples: 示例列表
            fixes: 修复方案列表
            best_practices: 最佳实践列表

        Returns:
            模式 ID
        """
        now = datetime.now().isoformat()
        with self._transaction() as cur:
            cur.execute("""
                INSERT INTO patterns (pattern_type, pattern_key, count, examples_json, fixes_json, best_practices_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pattern_type, pattern_key) DO UPDATE SET
                    count = count + excluded.count,
                    examples_json = excluded.examples_json,
                    fixes_json = CASE
                        WHEN excluded.fixes_json != '[]' THEN excluded.fixes_json
                        ELSE patterns.fixes_json
                    END,
                    best_practices_json = CASE
                        WHEN excluded.best_practices_json != '[]' THEN excluded.best_practices_json
                        ELSE patterns.best_practices_json
                    END,
                    updated_at = excluded.updated_at
            """, (
                pattern_type,
                pattern_key,
                count,
                json.dumps(examples or [], ensure_ascii=False),
                json.dumps(fixes or [], ensure_ascii=False),
                json.dumps(best_practices or [], ensure_ascii=False),
                now,
            ))
            return cur.lastrowid

    def get_pattern(self, pattern_type: str, pattern_key: str) -> Optional[dict]:
        """获取一条学习模式"""
        row = self._conn.execute(
            "SELECT * FROM patterns WHERE pattern_type = ? AND pattern_key = ?",
            (pattern_type, pattern_key)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def query_patterns(self, pattern_type: str = None, limit: int = 100) -> list[dict]:
        """查询学习模式"""
        if pattern_type:
            rows = self._conn.execute(
                "SELECT * FROM patterns WHERE pattern_type = ? ORDER BY count DESC LIMIT ?",
                (pattern_type, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM patterns ORDER BY count DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_pattern(self, pattern_type: str, pattern_key: str) -> bool:
        """删除一条学习模式"""
        with self._transaction() as cur:
            cur.execute(
                "DELETE FROM patterns WHERE pattern_type = ? AND pattern_key = ?",
                (pattern_type, pattern_key)
            )
            return cur.rowcount > 0

    def get_patterns_stats(self) -> dict:
        """获取学习模式统计"""
        rows = self._conn.execute("""
            SELECT pattern_type, COUNT(*) as cnt, SUM(count) as total_count
            FROM patterns
            GROUP BY pattern_type
        """).fetchall()

        stats = {}
        for r in rows:
            stats[r["pattern_type"]] = {
                "unique_patterns": r["cnt"],
                "total_occurrences": r["total_count"],
            }
        return stats

    # ============================================================
    # 改进建议 CRUD
    # ============================================================

    def add_improvement(self, suggestion: str) -> int:
        """添加改进建议"""
        with self._transaction() as cur:
            cur.execute("""
                INSERT INTO improvements (suggestion, implemented, created_at)
                VALUES (?, 0, ?)
            """, (suggestion, datetime.now().isoformat()))
            return cur.lastrowid

    def mark_improvement_done(self, improvement_id: int) -> bool:
        """标记改进建议已实施"""
        with self._transaction() as cur:
            cur.execute(
                "UPDATE improvements SET implemented = 1 WHERE id = ?",
                (improvement_id,)
            )
            return cur.rowcount > 0

    def get_improvements(self, unimplemented_only: bool = True) -> list[dict]:
        """获取改进建议"""
        if unimplemented_only:
            rows = self._conn.execute(
                "SELECT * FROM improvements WHERE implemented = 0 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM improvements ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_improvement(self, improvement_id: int) -> bool:
        """删除改进建议"""
        with self._transaction() as cur:
            cur.execute("DELETE FROM improvements WHERE id = ?", (improvement_id,))
            return cur.rowcount > 0

    # ============================================================
    # 数据迁移支持
    # ============================================================

    def mark_migration(self, source: str, status: str = "done"):
        """记录迁移状态"""
        with self._transaction() as cur:
            cur.execute(
                "INSERT INTO migrations (source, status, migrated_at) VALUES (?, ?, ?)",
                (source, status, datetime.now().isoformat())
            )

    def is_migrated(self, source: str) -> bool:
        """检查某个数据源是否已迁移"""
        row = self._conn.execute(
            "SELECT 1 FROM migrations WHERE source = ? AND status = 'done'",
            (source,)
        ).fetchone()
        return row is not None

    # ============================================================
    # 全局统计
    # ============================================================

    def get_all_stats(self) -> dict:
        """获取所有模块的统计信息"""
        return {
            "experiences": {
                "total": self.count_experiences(),
                "successes": self.count_experiences(success_only=True),
                "failures": self.count_experiences(success_only=False),
            },
            "memories": {
                "total": self.count_memories(),
                "short_term": self.count_memories(memory_type="short"),
                "long_term": self.count_memories(memory_type="long"),
            },
            "metrics": self.get_metrics_stats(),
            "logs": self.get_logs_stats(),
            "patterns": self.get_patterns_stats(),
            "improvements": {
                "pending": len(self.get_improvements(unimplemented_only=True)),
            },
        }

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _row_to_dict(row) -> dict:
        """将 sqlite3.Row 转换为字典，自动解析 JSON 字段"""
        if row is None:
            return None
        d = dict(row)

        # 解析 JSON 字段
        json_fields = [
            "steps_json", "tags_json", "data_json", "context_json",
            "params_json", "result_json",
            "examples_json", "fixes_json", "best_practices_json",
        ]
        for field in json_fields:
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        # boolean 字段
        for field in ("success", "implemented"):
            if field in d:
                d[field] = bool(d[field])

        # 去掉 _json 后缀的别名
        rename_map = {
            "steps_json": "steps",
            "tags_json": "tags",
            "data_json": "data",
            "context_json": "context",
            "params_json": "params",
            "result_json": "result",
            "examples_json": "examples",
            "fixes_json": "fixes",
            "best_practices_json": "best_practices",
        }
        for old_key, new_key in rename_map.items():
            if old_key in d:
                d[new_key] = d[old_key]
                # 保留原名，避免破坏已有代码
                # del d[old_key]

        return d

    def backup(self, backup_path: str = None) -> str:
        """
        备份数据库

        Args:
            backup_path: 备份路径，默认为 state/mi_hands_backup_YYYYMMDD.db

        Returns:
            备份文件路径
        """
        if not backup_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = str(STATE_DIR / f"mi_hands_backup_{ts}.db")

        # 使用 SQLite 在线备份，不锁库
        backup_conn = sqlite3.connect(backup_path)
        self._conn.backup(backup_conn)
        backup_conn.close()

        return backup_path
