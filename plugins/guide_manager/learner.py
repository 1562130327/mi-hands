"""学习引擎 - 自动学习新应用"""

import os
import re
import yaml
from typing import Dict, List, Any, Optional
from .local_scanner import LocalScanner
from .models import AppGuide, Operation, OperationStep


class Learner:
    """学习引擎"""

    def __init__(self):
        self._local_scanner = LocalScanner()

    async def learn_app(self, app_path: str) -> Optional[AppGuide]:
        """学习新应用"""
        try:
            # 1. 扫描本地文件
            local_info = await self._scan_local(app_path)

            # 2. 提取应用信息
            app_info = self._extract_app_info(app_path, local_info)

            # 3. 生成操作指南
            guide = self._generate_guide(app_info)

            return guide
        except Exception as e:
            print(f"学习应用失败: {e}")
            return None

    async def _scan_local(self, app_path: str) -> Dict[str, Any]:
        """扫描本地文件"""
        result = {
            "readme_files": [],
            "config_files": [],
            "doc_files": [],
            "help_files": []
        }

        # 扫描安装目录
        if os.path.isdir(app_path):
            result = self._local_scanner.scan_directory(app_path)

        # 扫描桌面快捷方式
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop_path):
            for file in os.listdir(desktop_path):
                if file.endswith(".lnk"):
                    result["shortcuts"] = result.get("shortcuts", [])
                    result["shortcuts"].append(os.path.join(desktop_path, file))

        return result

    def _extract_app_info(self, app_path: str, local_info: Dict) -> Dict[str, Any]:
        """提取应用信息"""
        info = {
            "name": os.path.basename(app_path),
            "version": "1.0.0",
            "process_name": os.path.basename(app_path),
            "install_path": app_path
        }

        # 从 README 提取信息
        for readme in local_info.get("readme_files", []):
            readme_info = self._local_scanner.extract_info(readme)
            if readme_info.get("name"):
                info["name"] = readme_info["name"]
            if readme_info.get("version"):
                info["version"] = readme_info["version"]

        # 从配置文件提取信息
        for config in local_info.get("config_files", []):
            config_info = self._extract_config_info(config)
            if config_info:
                info.update(config_info)

        return info

    def _extract_config_info(self, config_path: str) -> Dict[str, Any]:
        """从配置文件提取信息"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 尝试解析 YAML
            if config_path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    return data

            # 尝试解析 JSON
            if config_path.endswith(".json"):
                import json
                data = json.loads(content)
                if isinstance(data, dict):
                    return data

            # 尝试解析 INI
            if config_path.endswith(".ini"):
                import configparser
                config = configparser.ConfigParser()
                config.read(config_path)
                result = {}
                for section in config.sections():
                    result[section] = dict(config[section])
                return result

            return {}
        except Exception:
            return {}

    def _generate_guide(self, app_info: Dict) -> AppGuide:
        """生成操作指南"""
        # 创建基本操作
        operations = {}

        # 添加打开操作
        operations["open"] = Operation(
            name="open",
            description=f"打开 {app_info['name']}",
            steps=[
                OperationStep(action="hotkey", key=["win", "r"]),
                OperationStep(action="type_text", text=app_info["process_name"]),
                OperationStep(action="press_key", key="enter"),
                OperationStep(action="wait_for_element", target=f"{app_info['name']} 窗口", timeout=10)
            ]
        )

        # 创建操作指南
        guide = AppGuide(
            name=app_info["name"],
            version=app_info["version"],
            process_name=app_info["process_name"],
            install_paths=[app_info["install_path"]],
            operations=operations
        )

        return guide

    async def learn_from_uia(self, app_name: str, uia_tree: Dict) -> Dict[str, Any]:
        """从 UIA 树学习"""
        result = {
            "buttons": [],
            "inputs": [],
            "menus": []
        }

        # 解析 UIA 树
        self._parse_uia_tree(uia_tree, result)

        return result

    def _parse_uia_tree(self, node: Dict, result: Dict, path: List[int] = None):
        """解析 UIA 树"""
        if path is None:
            path = []

        # 提取控件信息
        control_type = node.get("type", "")
        name = node.get("name", "")

        if control_type == "ButtonControl":
            result["buttons"].append({
                "name": name,
                "path": path.copy()
            })
        elif control_type == "EditControl":
            result["inputs"].append({
                "name": name,
                "path": path.copy()
            })
        elif control_type == "MenuControl":
            result["menus"].append({
                "name": name,
                "path": path.copy()
            })

        # 递归处理子节点
        for i, child in enumerate(node.get("children", [])):
            path.append(i)
            self._parse_uia_tree(child, result, path)
            path.pop()

    async def learn_from_web(self, app_name: str) -> Dict[str, Any]:
        """从网络学习"""
        # 这里可以调用 WebSearch 或 WebFetch
        # 暂时返回空字典
        return {}

    def merge_learned_info(self, local_info: Dict, uia_info: Dict, web_info: Dict) -> Dict:
        """合并学习到的信息"""
        merged = {
            "name": local_info.get("name", "Unknown"),
            "version": local_info.get("version", "1.0.0"),
            "process_name": local_info.get("process_name", ""),
            "operations": {}
        }

        # 合并 UIA 信息
        if uia_info:
            # 为每个按钮创建操作
            for button in uia_info.get("buttons", []):
                op_name = f"click_{button['name'].lower().replace(' ', '_')}"
                merged["operations"][op_name] = {
                    "description": f"点击 {button['name']}",
                    "steps": [
                        {"action": "click", "target": button["name"], "path": button["path"]}
                    ]
                }

        # 合并网络信息
        if web_info:
            merged.update(web_info)

        return merged
