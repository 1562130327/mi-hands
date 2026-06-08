"""
ScriptExecutor - 脚本执行

职责：
1. 安全执行 Python 代码
2. 安全执行 Shell 命令
3. 限制执行时间和资源

安全策略：白名单机制（只允许安全的操作）
"""

import subprocess
import sys
import os
import re
import tempfile
from typing import Optional, Set
from pathlib import Path


# 安全限制
MAX_EXECUTION_TIME = 60  # 秒
MAX_OUTPUT_LENGTH = 5000
MAX_ERROR_LENGTH = 2000

# ============================================================
# 白名单机制（只允许这些模块和函数）
# ============================================================

# 允许的 Python 模块（精确匹配 import 语句）
ALLOWED_PYTHON_MODULES: Set[str] = {
    # 标准库
    "math", "json", "re", "datetime", "time", "random",
    "collections", "itertools", "functools", "string",
    "statistics", "decimal", "fractions", "enum",
    "pathlib", "typing", "dataclasses",
    # 第三方
    "PIL", "pillow", "numpy", "np",
    "requests", "httpx",
}

# 允许的危险操作（特定上下文中安全）
ALLOWED_DANGEROUS_CALLS = {
    "pathlib.Path",  # 文件路径操作（安全）
}

# 禁止的危险模块（黑名单作为补充）
BLOCKED_MODULES: Set[str] = {
    "os.system", "os.popen", "os.exec",
    "subprocess.call", "subprocess.run", "subprocess.Popen",
    "ctypes.windll", "ctypes.cdll",
    "win32api", "win32gui", "win32process",
    "importlib.import_module",
}

# 禁止的系统路径
BLOCKED_PATHS = {
    "/etc", "/sys", "/proc", "/dev",
    "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",
}


class ScriptExecutor:
    """
    脚本执行器

    安全执行代码，有以下限制：
    - 执行时间限制
    - 白名单模块（只允许安全的模块）
    - 输出长度限制
    - 路径限制（禁止系统目录）
    """

    def __init__(self, allowed_modules: Set[str] = None):
        """
        初始化脚本执行器

        Args:
            allowed_modules: 额外允许的模块（可选）
        """
        self._allowed_modules = ALLOWED_PYTHON_MODULES.copy()
        if allowed_modules:
            self._allowed_modules.update(allowed_modules)

    def execute_python(self, code: str, timeout: int = None) -> dict:
        """
        执行 Python 代码

        Args:
            code: Python 代码
            timeout: 超时时间（秒）

        Returns:
            {"success": bool, "output": str, "error": str}
        """
        timeout = timeout or MAX_EXECUTION_TIME

        # 安全检查（白名单）
        safety_result = self._check_code_safety(code)
        if not safety_result["safe"]:
            return {
                "success": False,
                "output": "",
                "error": f"安全检查失败: {safety_result['reason']}"
            }

        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
            ) as f:
                f.write(code)
                temp_file = f.name

            try:
                # 执行
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(Path.home()),
                )

                return {
                    "success": result.returncode == 0,
                    "output": result.stdout[:MAX_OUTPUT_LENGTH],
                    "error": result.stderr[:MAX_ERROR_LENGTH] if result.stderr else "",
                }

            finally:
                # 清理临时文件
                os.unlink(temp_file)

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"执行超时 ({timeout} 秒)"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

    def execute_shell(self, command: str, timeout: int = None) -> dict:
        """
        执行 Shell 命令

        Args:
            command: Shell 命令
            timeout: 超时时间（秒）

        Returns:
            {"success": bool, "output": str, "error": str}
        """
        timeout = timeout or MAX_EXECUTION_TIME

        # 安全检查（白名单）
        safety_result = self._check_command_safety(command)
        if not safety_result["safe"]:
            return {
                "success": False,
                "output": "",
                "error": f"安全检查失败: {safety_result['reason']}"
            }

        try:
            # 避免 shell=True，使用列表形式
            if isinstance(command, str):
                # 简单拆分（处理引号）
                import shlex
                cmd_list = shlex.split(command)
            else:
                cmd_list = command

            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path.home()),
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout[:MAX_OUTPUT_LENGTH],
                "error": result.stderr[:MAX_ERROR_LENGTH] if result.stderr else "",
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"命令超时 ({timeout} 秒)"
            }
        except FileNotFoundError:
            return {
                "success": False,
                "output": "",
                "error": f"命令未找到: {cmd_list[0] if cmd_list else command}"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

    def execute_batch(self, script_path: str) -> dict:
        """
        执行批处理脚本

        Args:
            script_path: 脚本路径

        Returns:
            {"success": bool, "output": str, "error": str}
        """
        # 路径安全检查
        abs_path = Path(script_path).resolve()
        if not abs_path.exists():
            return {
                "success": False,
                "output": "",
                "error": f"脚本不存在: {script_path}"
            }

        # 检查是否在禁止的路径中
        for blocked in BLOCKED_PATHS:
            if str(abs_path).startswith(blocked):
                return {
                    "success": False,
                    "output": "",
                    "error": f"禁止执行系统目录中的脚本: {blocked}"
                }

        try:
            result = subprocess.run(
                [str(abs_path)],
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout[:MAX_OUTPUT_LENGTH],
                "error": result.stderr[:MAX_ERROR_LENGTH] if result.stderr else "",
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"脚本执行超时 ({MAX_EXECUTION_TIME} 秒)"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

    # ============================================================
    # 安全检查（白名单机制）
    # ============================================================

    def _check_code_safety(self, code: str) -> dict:
        """
        检查代码安全性（白名单机制）

        Returns:
            {"safe": bool, "reason": str}
        """
        # 1. 检查禁止的模块调用
        for blocked in BLOCKED_MODULES:
            if blocked in code:
                return {"safe": False, "reason": f"禁止调用: {blocked}"}

        # 2. 检查 import 语句（白名单）
        import_pattern = r'(?:from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import|import\s+([a-zA-Z_][a-zA-Z0-9_]*))'
        imports = re.findall(import_pattern, code)
        for match in imports:
            module = match[0] or match[1]
            # 去掉别名（如 import numpy as np -> numpy）
            module = module.split('.')[0].strip()
            if module not in self._allowed_modules:
                return {"safe": False, "reason": f"未授权的模块: {module}"}

        # 3. 检查危险函数调用
        dangerous_patterns = [
            (r'\bexec\s*\(', "exec()"),
            (r'\beval\s*\(', "eval()"),
            (r'__import__\s*\(', "__import__()"),
            (r'\bcompile\s*\(', "compile()"),
            (r'\bglobals\s*\(', "globals()"),
            (r'\blocals\s*\(', "locals()"),
            (r'\bvars\s*\(', "vars()"),
            (r'\bgetattr\s*\(', "getattr()"),
            (r'\bsetattr\s*\(', "setattr()"),
            (r'\bdelattr\s*\(', "delattr()"),
        ]
        for pattern, name in dangerous_patterns:
            if re.search(pattern, code):
                return {"safe": False, "reason": f"禁止调用: {name}"}

        # 4. 检查系统路径访问
        for path in BLOCKED_PATHS:
            if path in code:
                return {"safe": False, "reason": f"禁止访问系统路径: {path}"}

        # 5. 检查文件操作（限制范围）
        dangerous_file_ops = [
            (r"open\s*\(\s*['\"]\/", "读取系统文件"),
            (r"os\.remove\s*\(", "删除文件"),
            (r"shutil\.rmtree\s*\(", "删除目录"),
            (r"os\.rmdir\s*\(", "删除目录"),
        ]
        for pattern, desc in dangerous_file_ops:
            if re.search(pattern, code):
                return {"safe": False, "reason": f"禁止操作: {desc}"}

        return {"safe": True, "reason": ""}

    def _check_command_safety(self, command: str) -> dict:
        """
        检查命令安全性（白名单机制）

        Returns:
            {"safe": bool, "reason": str}
        """
        cmd_lower = command.lower()

        # 允许的命令前缀
        allowed_prefixes = [
            "python", "pip", "dir", "ls", "cat", "type",
            "echo", "date", "time", "whoami", "hostname",
        ]

        # 检查是否以允许的命令开头
        first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
        if first_word not in allowed_prefixes:
            return {"safe": False, "reason": f"未授权的命令: {first_word}"}

        # 检查危险命令模式
        dangerous_patterns = [
            (r'\bformat\b', "格式化磁盘"),
            (r'\bdel\s+\/[sq]', "强制删除"),
            (r'\brmdir\s+\/[sq]', "强制删除目录"),
            (r'\brm\s+-rf', "强制删除"),
            (r'\bdd\s+if=', "磁盘操作"),
            (r'\bmkfs\b', "格式化文件系统"),
            (r'\bshutdown\b', "关机"),
            (r'\breboot\b', "重启"),
            (r'\bnet\s+user\b', "用户管理"),
            (r'\breg\s+delete\b', "注册表删除"),
        ]
        for pattern, desc in dangerous_patterns:
            if re.search(pattern, cmd_lower):
                return {"safe": False, "reason": f"禁止操作: {desc}"}

        # 检查系统路径
        for path in BLOCKED_PATHS:
            if path.lower() in cmd_lower:
                return {"safe": False, "reason": f"禁止访问系统路径: {path}"}

        return {"safe": True, "reason": ""}
