"""
FileOperations - 文件操作

职责：
1. 读取文件
2. 写入文件
3. 列出目录
4. 搜索文件
5. 复制/删除文件

安全策略：路径白名单（只允许在指定目录内操作）
"""

import os
import shutil
import glob
from typing import Optional, Set
from pathlib import Path


# 禁止访问的系统路径
BLOCKED_PATHS = {
    "C:\\Windows", "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",
    "C:\\Program Files", "C:\\Program Files (x86)",
    "/etc", "/sys", "/proc", "/dev", "/boot", "/sbin", "/bin",
}


class FileOperations:
    """
    文件操作工具

    提供安全的文件操作接口，限制操作范围在 base_path 内
    """

    def __init__(self, base_path: str = None, allowed_paths: Set[str] = None):
        """
        初始化

        Args:
            base_path: 基础路径（限制操作范围，默认用户主目录）
            allowed_paths: 额外允许的路径（可选）
        """
        self.base_path = Path(base_path) if base_path else Path.home()
        self._allowed_paths = {str(self.base_path.resolve())}
        if allowed_paths:
            self._allowed_paths.update(allowed_paths)

    def _resolve_path(self, path: str) -> Path:
        """解析路径"""
        p = Path(path)
        if not p.is_absolute():
            p = self.base_path / p
        return p.resolve()

    def _is_path_allowed(self, path: Path) -> bool:
        """
        检查路径是否允许访问

        规则：
        1. 必须在 base_path 或 allowed_paths 内
        2. 不能是系统目录
        """
        resolved = path.resolve()

        # 检查系统路径
        for blocked in BLOCKED_PATHS:
            if str(resolved).startswith(blocked):
                return False

        # 检查是否在允许的路径内
        for allowed in self._allowed_paths:
            if str(resolved).startswith(allowed):
                return True

        return False

    def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        """
        读取文件

        Args:
            path: 文件路径
            encoding: 编码

        Returns:
            {"success": bool, "content": str, "error": str}
        """
        try:
            file_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(file_path):
                return {"success": False, "content": "", "error": f"禁止访问该路径: {path}"}

            if not file_path.exists():
                return {"success": False, "content": "", "error": f"文件不存在: {path}"}

            if not file_path.is_file():
                return {"success": False, "content": "", "error": f"不是文件: {path}"}

            # 限制文件大小（最大 1MB）
            if file_path.stat().st_size > 1024 * 1024:
                return {"success": False, "content": "", "error": "文件太大 (>1MB)"}

            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            return {"success": True, "content": content, "error": ""}

        except UnicodeDecodeError:
            return {"success": False, "content": "", "error": "文件编码错误，请指定正确的编码"}
        except Exception as e:
            return {"success": False, "content": "", "error": str(e)}

    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        """
        写入文件

        Args:
            path: 文件路径
            content: 文件内容
            encoding: 编码

        Returns:
            {"success": bool, "error": str}
        """
        try:
            file_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(file_path):
                return {"success": False, "error": f"禁止写入该路径: {path}"}

            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)

            return {"success": True, "error": ""}

        except PermissionError:
            return {"success": False, "error": f"没有写入权限: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_file(self, path: str, content: str, encoding: str = "utf-8") -> dict:
        """
        追加内容到文件

        Args:
            path: 文件路径
            content: 要追加的内容
            encoding: 编码

        Returns:
            {"success": bool, "error": str}
        """
        try:
            file_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(file_path):
                return {"success": False, "error": f"禁止追加到该路径: {path}"}

            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)

            return {"success": True, "error": ""}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_dir(self, path: str = ".", pattern: str = None) -> dict:
        """
        列出目录内容

        Args:
            path: 目录路径
            pattern: 通配符模式（如 "*.txt"）

        Returns:
            {"success": bool, "items": list, "error": str}
        """
        try:
            dir_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(dir_path):
                return {"success": False, "items": [], "error": f"禁止访问该路径: {path}"}

            if not dir_path.exists():
                return {"success": False, "items": [], "error": f"目录不存在: {path}"}

            if not dir_path.is_dir():
                return {"success": False, "items": [], "error": f"不是目录: {path}"}

            if pattern:
                items = list(dir_path.glob(pattern))
            else:
                items = list(dir_path.iterdir())

            # 转换为相对路径字符串
            result = []
            for item in items:
                try:
                    rel_path = item.relative_to(dir_path)
                    result.append({
                        "name": str(rel_path),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
                except Exception:
                    continue

            return {"success": True, "items": result, "error": ""}

        except Exception as e:
            return {"success": False, "items": [], "error": str(e)}

    def search_files(self, pattern: str, path: str = ".") -> dict:
        """
        搜索文件

        Args:
            pattern: 搜索模式（如 "*.py", "**/*.json"）
            path: 搜索路径

        Returns:
            {"success": bool, "files": list, "error": str}
        """
        try:
            search_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(search_path):
                return {"success": False, "files": [], "error": f"禁止搜索该路径: {path}"}

            if not search_path.exists():
                return {"success": False, "files": [], "error": f"路径不存在: {path}"}

            # 使用 glob 搜索
            files = list(search_path.glob(pattern))

            # 转换为字符串
            result = [str(f) for f in files if f.is_file()]

            return {"success": True, "files": result[:100], "error": ""}  # 限制结果数量

        except Exception as e:
            return {"success": False, "files": [], "error": str(e)}

    def copy_file(self, src: str, dst: str) -> dict:
        """
        复制文件

        Args:
            src: 源路径
            dst: 目标路径

        Returns:
            {"success": bool, "error": str}
        """
        try:
            src_path = self._resolve_path(src)
            dst_path = self._resolve_path(dst)

            # 路径安全检查
            if not self._is_path_allowed(src_path):
                return {"success": False, "error": f"禁止读取源路径: {src}"}
            if not self._is_path_allowed(dst_path):
                return {"success": False, "error": f"禁止写入目标路径: {dst}"}

            if not src_path.exists():
                return {"success": False, "error": f"源文件不存在: {src}"}

            # 确保目标目录存在
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
            else:
                shutil.copy2(str(src_path), str(dst_path))

            return {"success": True, "error": ""}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_file(self, path: str, confirm: bool = False) -> dict:
        """
        删除文件

        Args:
            path: 文件路径
            confirm: 必须为 True 才能删除（安全确认）

        Returns:
            {"success": bool, "error": str}
        """
        try:
            file_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(file_path):
                return {"success": False, "error": f"禁止删除该路径: {path}"}

            # 安全确认
            if not confirm:
                return {"success": False, "error": "删除操作需要确认，请设置 confirm=True"}

            if not file_path.exists():
                return {"success": False, "error": f"文件不存在: {path}"}

            if file_path.is_dir():
                # 限制：不允许删除非空目录
                if any(file_path.iterdir()):
                    return {"success": False, "error": "目录非空，请先清空目录"}
                file_path.rmdir()
            else:
                file_path.unlink()

            return {"success": True, "error": ""}

        except PermissionError:
            return {"success": False, "error": f"没有删除权限: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_file_info(self, path: str) -> dict:
        """
        获取文件信息

        Args:
            path: 文件路径

        Returns:
            {"success": bool, "info": dict, "error": str}
        """
        try:
            file_path = self._resolve_path(path)

            # 路径安全检查
            if not self._is_path_allowed(file_path):
                return {"success": False, "info": {}, "error": f"禁止访问该路径: {path}"}

            if not file_path.exists():
                return {"success": False, "info": {}, "error": f"文件不存在: {path}"}

            stat = file_path.stat()

            info = {
                "name": file_path.name,
                "path": str(file_path),
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }

            return {"success": True, "info": info, "error": ""}

        except Exception as e:
            return {"success": False, "info": {}, "error": str(e)}
