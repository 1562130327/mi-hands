"""
数据迁移脚本 — JSON 状态文件 -> SQLite

把分散在多个目录的 JSON 状态文件统一导入 state/mi_hands.db。

用法：
    python scripts/migrate_state_to_sqlite.py

迁移的数据：
1. memory/long_term.json      -> memories 表
2. experience/experiences.json -> experiences 表
3. learning/patterns.json      -> patterns 表 + improvements
4. metrics/metrics.json        -> metrics 表
5. logs/actions_*.json         -> logs 表
6. state/rollback_stack.json   -> logs 表 (rollback 类型)

执行后原 JSON 文件会被重命名为 *.json.bak 保留备份。
"""

import json
import sys
import shutil
from pathlib import Path
from datetime import datetime

# 把项目根目录加入 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from v3.core.state_manager import StateManager


# ============================================================
# 迁移函数
# ============================================================

def migrate_long_term_memory(sm: StateManager):
    """迁移 memory/long_term.json -> memories 表"""
    src = PROJECT_ROOT / "memory" / "long_term.json"
    if not src.exists():
        print("  [skip] memory/long_term.json 不存在")
        return 0

    print("  [migrate] memory/long_term.json -> memories")
    count = 0

    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        for category, entries in data.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                sm.add_memory(
                    memory_data=entry.get("data", {}),
                    memory_type="long",
                    category=category,
                    action=entry.get("data", {}).get("action", ""),
                )
                count += 1

        # 备份原文件
        backup_path = src.with_suffix(".json.bak")
        shutil.copy2(src, backup_path)
        print(f"    -> 迁移 {count} 条记忆，已备份到 {backup_path.name}")
    except Exception as e:
        print(f"    -> 迁移失败: {e}")

    return count


def migrate_experiences(sm: StateManager):
    """迁移 experience/experiences.json -> experiences 表"""
    src = PROJECT_ROOT / "experience" / "experiences.json"
    if not src.exists():
        print("  [skip] experience/experiences.json 不存在")
        return 0

    print("  [migrate] experience/experiences.json -> experiences")
    count = 0

    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        for exp_id, exp_dict in data.items():
            sm.add_experience(exp_dict)
            count += 1

        # 备份原文件
        backup_path = src.with_suffix(".json.bak")
        shutil.copy2(src, backup_path)
        print(f"    -> 迁移 {count} 条经验，已备份到 {backup_path.name}")
    except Exception as e:
        print(f"    -> 迁移失败: {e}")

    # 也迁移 index.json
    idx_src = PROJECT_ROOT / "experience" / "index.json"
    if idx_src.exists():
        backup_path = idx_src.with_suffix(".json.bak")
        shutil.copy2(idx_src, backup_path)
        print(f"    -> index.json 已备份")

    return count


def migrate_patterns(sm: StateManager):
    """迁移 learning/patterns.json -> patterns + improvements 表"""
    src = PROJECT_ROOT / "learning" / "patterns.json"
    if not src.exists():
        print("  [skip] learning/patterns.json 不存在")
        return 0

    print("  [migrate] learning/patterns.json -> patterns + improvements")
    count = 0

    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 迁移错误模式
        for pattern_key, pattern_data in data.get("error_patterns", {}).items():
            sm.upsert_pattern(
                pattern_type="error",
                pattern_key=pattern_key,
                count=pattern_data.get("count", 0),
                examples=pattern_data.get("examples", []),
                fixes=pattern_data.get("fixes", []),
            )
            count += 1

        # 迁移成功模式
        for pattern_key, pattern_data in data.get("success_patterns", {}).items():
            sm.upsert_pattern(
                pattern_type="success",
                pattern_key=pattern_key,
                count=pattern_data.get("count", 0),
                examples=pattern_data.get("examples", []),
                best_practices=pattern_data.get("best_practices", []),
            )
            count += 1

        # 迁移改进建议
        for item in data.get("improvements", []):
            sm.add_improvement(item.get("suggestion", ""))
            if item.get("implemented"):
                improvements = sm.get_improvements(unimplemented_only=False)
                if improvements:
                    sm.mark_improvement_done(improvements[-1]["id"])

        # 备份原文件
        backup_path = src.with_suffix(".json.bak")
        shutil.copy2(src, backup_path)
        print(f"    -> 迁移 {count} 个模式 + 改进建议，已备份到 {backup_path.name}")
    except Exception as e:
        print(f"    -> 迁移失败: {e}")

    return count


def migrate_metrics(sm: StateManager):
    """迁移 metrics/metrics.json -> metrics 表"""
    src = PROJECT_ROOT / "metrics" / "metrics.json"
    if not src.exists():
        print("  [skip] metrics/metrics.json 不存在")
        return 0

    print("  [migrate] metrics/metrics.json -> metrics")
    count = 0

    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 迁移操作时间记录
        for item in data.get("action_times", []):
            sm.add_metric(
                action_type=item.get("action", "unknown"),
                duration=item.get("duration", 0.0),
                success=item.get("success", True),
                error_type="",
            )
            count += 1

        # 备份原文件
        backup_path = src.with_suffix(".json.bak")
        shutil.copy2(src, backup_path)
        print(f"    -> 迁移 {count} 条指标，已备份到 {backup_path.name}")
    except Exception as e:
        print(f"    -> 迁移失败: {e}")

    return count


def migrate_action_logs(sm: StateManager):
    """迁移 logs/actions_*.json -> logs 表"""
    logs_dir = PROJECT_ROOT / "logs"
    if not logs_dir.exists():
        print("  [skip] logs/ 目录不存在")
        return 0

    print("  [migrate] logs/actions_*.json -> logs")
    count = 0

    try:
        for log_file in sorted(logs_dir.glob("actions_*.json")):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)

                for entry in entries:
                    sm.add_log(
                        action=entry.get("action", "unknown"),
                        params=entry.get("params", {}),
                        result=entry.get("result", {}),
                        duration=entry.get("duration", 0.0),
                        success=entry.get("success", False),
                    )
                    count += 1

                # 备份原文件
                backup_path = log_file.with_suffix(".json.bak")
                shutil.copy2(log_file, backup_path)
                print(f"    -> {log_file.name}: {len(entries)} 条日志")
            except Exception as e:
                print(f"    -> {log_file.name} 迁移失败: {e}")
    except Exception as e:
        print(f"    -> 扫描日志目录失败: {e}")

    print(f"    -> 共迁移 {count} 条日志")
    return count


def migrate_rollback_stack(sm: StateManager):
    """迁移 state/rollback_stack.json -> logs 表 (rollback 类型)"""
    src = PROJECT_ROOT / "state" / "rollback_stack.json"
    if not src.exists():
        print("  [skip] state/rollback_stack.json 不存在")
        return 0

    print("  [migrate] state/rollback_stack.json -> logs (rollback)")
    count = 0

    try:
        with open(src, "r", encoding="utf-8") as f:
            stack = json.load(f)

        for entry in stack:
            sm.add_log(
                action=f"__rollback__:{entry.get('action', 'unknown')}",
                params={"action": entry.get("action", "unknown")},
                result=entry.get("state", {}),
                success=True,
            )
            count += 1

        # 备份原文件
        backup_path = src.with_suffix(".json.bak")
        shutil.copy2(src, backup_path)
        print(f"    -> 迁移 {count} 条回滚记录，已备份到 {backup_path.name}")
    except Exception as e:
        print(f"    -> 迁移失败: {e}")

    return count


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 50)
    print("MI Hands 数据迁移: JSON -> SQLite")
    print("=" * 50)
    print()

    sm = StateManager()
    total = 0

    # 逐个迁移
    total += migrate_long_term_memory(sm)
    total += migrate_experiences(sm)
    total += migrate_patterns(sm)
    total += migrate_metrics(sm)
    total += migrate_action_logs(sm)
    total += migrate_rollback_stack(sm)

    # 记录迁移
    sm.mark_migration("json_files")

    print()
    print("=" * 50)
    print(f"迁移完成！共迁移 {total} 条数据")
    print()

    # 显示统计
    stats = sm.get_all_stats()
    print("数据库统计:")
    for module, data in stats.items():
        print(f"  {module}: {data}")

    print()
    print("原 JSON 文件已备份为 .json.bak")
    print("数据库位置: state/mi_hands.db")

    sm.close()


if __name__ == "__main__":
    main()
