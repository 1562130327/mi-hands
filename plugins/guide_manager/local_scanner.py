"""本地文件扫描器"""

import os
import re
from typing import Dict, List, Any


class LocalScanner:
    """本地文件扫描器"""

    def scan_directory(self, directory: str) -> Dict[str, List[str]]:
        """扫描目录，查找文档和配置文件"""
        result = {
            "readme_files": [],
            "config_files": [],
            "doc_files": [],
            "help_files": []
        }

        for root, dirs, files in os.walk(directory):
            for file in files:
                file_lower = file.lower()
                full_path = os.path.join(root, file)

                if file_lower.startswith("readme"):
                    result["readme_files"].append(full_path)
                elif file_lower.endswith((".ini", ".yaml", ".yml", ".json", ".toml")):
                    result["config_files"].append(full_path)
                elif file_lower.endswith((".txt", ".md", ".html", ".chm")):
                    result["doc_files"].append(full_path)
                elif "help" in file_lower:
                    result["help_files"].append(full_path)

        return result

    def extract_info(self, file_path: str) -> Dict[str, Any]:
        """从文件中提取应用信息"""
        info = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 尝试提取版本号
            version_match = re.search(r"v?(\d+\.\d+\.\d+)", content)
            if version_match:
                info["version"] = version_match.group(1)

            # 尝试提取应用名称（第一行通常是名称）
            lines = content.strip().split("\n")
            if lines:
                info["name"] = lines[0].strip()

        except Exception:
            pass

        return info
