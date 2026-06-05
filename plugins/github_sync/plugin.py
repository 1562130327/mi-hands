"""GitHub 同步插件实现"""

import os
import json
import subprocess
from typing import Dict, List, Optional, Any
from core.interfaces import PluginInterface


class GitHubSyncPlugin(PluginInterface):
    """GitHub 同步插件"""

    name = "github_sync"
    version = "1.0.0"
    dependencies = []

    def __init__(self, repo_url: str = None, local_dir: str = "app_guides"):
        self._repo_url = repo_url or "https://github.com/1562130327/mi-hands-guides.git"
        self._local_dir = local_dir
        self._repo_dir = os.path.join(local_dir, ".git")
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化插件"""
        try:
            # 检查是否已初始化
            if os.path.exists(self._repo_dir):
                self._initialized = True
                return True

            # 如果本地目录不存在，创建它
            os.makedirs(self._local_dir, exist_ok=True)

            self._initialized = True
            return True
        except Exception as e:
            print(f"GitHub 同步插件初始化失败: {e}")
            return False

    async def shutdown(self):
        """关闭插件"""
        pass

    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        return {
            "name": self.name,
            "version": self.version,
            "initialized": self._initialized,
            "repo_url": self._repo_url,
            "local_dir": self._local_dir
        }

    async def clone_repo(self) -> bool:
        """克隆仓库"""
        try:
            # 如果目录已存在，先删除
            if os.path.exists(self._repo_dir):
                import shutil
                shutil.rmtree(self._repo_dir)

            # 克隆仓库
            result = subprocess.run(
                ["git", "clone", self._repo_url, self._local_dir],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self._initialized = True
                return True
            else:
                print(f"克隆仓库失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"克隆仓库异常: {e}")
            return False

    async def pull_updates(self) -> bool:
        """拉取更新"""
        try:
            if not os.path.exists(self._repo_dir):
                return await self.clone_repo()

            result = subprocess.run(
                ["git", "pull"],
                cwd=self._local_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            return result.returncode == 0
        except Exception as e:
            print(f"拉取更新异常: {e}")
            return False

    async def push_guide(self, guide_name: str, guide_content: str) -> bool:
        """推送操作指南到 GitHub"""
        try:
            # 匿名化处理
            anonymized_content = self._anonymize(guide_content)

            # 写入文件
            file_path = os.path.join(self._local_dir, f"{guide_name}.yaml")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(anonymized_content)

            # 添加到 git
            subprocess.run(
                ["git", "add", f"{guide_name}.yaml"],
                cwd=self._local_dir,
                capture_output=True,
                text=True
            )

            # 提交
            subprocess.run(
                ["git", "commit", "-m", f"feat: add {guide_name} guide"],
                cwd=self._local_dir,
                capture_output=True,
                text=True
            )

            # 推送
            result = subprocess.run(
                ["git", "push"],
                cwd=self._local_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            return result.returncode == 0
        except Exception as e:
            print(f"推送指南异常: {e}")
            return False

    async def get_guide_from_github(self, app_name: str) -> Optional[str]:
        """从 GitHub 获取操作指南"""
        try:
            # 先拉取最新更新
            await self.pull_updates()

            # 读取文件
            file_path = os.path.join(self._local_dir, f"{app_name}.yaml")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"获取指南异常: {e}")
            return None

    async def list_guides_from_github(self) -> List[str]:
        """列出 GitHub 上的所有操作指南"""
        try:
            # 先拉取最新更新
            await self.pull_updates()

            # 列出所有 yaml 文件
            guides = []
            for file in os.listdir(self._local_dir):
                if file.endswith(".yaml"):
                    guides.append(file[:-5])
            return guides
        except Exception as e:
            print(f"列出指南异常: {e}")
            return []

    def _anonymize(self, content: str) -> str:
        """匿名化处理"""
        import re

        # 移除用户名
        content = re.sub(r'C:\\Users\\[^\\]+', r'C:\\Users\\User', content)

        # 移除邮箱
        content = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'user@example.com', content)

        # 移除 IP 地址
        content = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '192.168.1.1', content)

        # 移除密码（假设密码在引号中）
        content = re.sub(r'password["\s]*[:=]["\s]*[^"]+', 'password: "***"', content)

        return content

    async def validate_guide(self, guide_content: str) -> Dict[str, Any]:
        """验证操作指南格式"""
        try:
            import yaml
            data = yaml.safe_load(guide_content)

            # 检查必填字段
            required_fields = ["metadata", "identity", "operations"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                return {
                    "valid": False,
                    "errors": [f"缺少必填字段: {', '.join(missing_fields)}"]
                }

            # 检查 metadata
            metadata = data.get("metadata", {})
            if "name" not in metadata:
                return {
                    "valid": False,
                    "errors": ["metadata 缺少 name 字段"]
                }

            # 检查 identity
            identity = data.get("identity", {})
            if "process_name" not in identity:
                return {
                    "valid": False,
                    "errors": ["identity 缺少 process_name 字段"]
                }

            return {"valid": True, "errors": []}
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"YAML 解析错误: {str(e)}"]
            }
