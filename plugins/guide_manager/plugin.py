"""操作指南管理插件实现"""

import os
import sys
from typing import Dict, List, Optional, Any
from core.interfaces import GuidePluginInterface
from .models import AppGuide


class GuideManagerPlugin(GuidePluginInterface):
    """操作指南管理插件"""

    name = "guide_manager"
    version = "1.0.0"
    dependencies = []

    def __init__(self, guides_dir: str = None):
        if guides_dir is None:
            # 尝试多个路径
            possible_paths = [
                "app_guides",  # 相对路径（开发模式）
                os.path.join(os.path.dirname(__file__), "..", "..", "app_guides"),  # 包内路径
                os.path.join(sys.prefix, "app_guides"),  # pip 安装路径
            ]
            for path in possible_paths:
                if os.path.exists(path) and os.listdir(path):
                    guides_dir = path
                    break
            else:
                guides_dir = "app_guides"  # 默认路径

        self._guides_dir = guides_dir
        self._guides: Dict[str, AppGuide] = {}

    async def initialize(self) -> bool:
        """初始化插件"""
        # 确保目录存在
        os.makedirs(self._guides_dir, exist_ok=True)

        # 加载已有的操作指南
        self._load_guides()
        return True

    async def shutdown(self):
        """关闭插件"""
        pass

    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        return {
            "name": self.name,
            "version": self.version,
            "guides_count": len(self._guides)
        }

    def _load_guides(self):
        """加载所有操作指南"""
        if not os.path.exists(self._guides_dir):
            return

        for filename in os.listdir(self._guides_dir):
            if filename.endswith(".yaml"):
                guide_name = filename[:-5]
                filepath = os.path.join(self._guides_dir, filename)

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        yaml_str = f.read()
                    guide = AppGuide.from_yaml(yaml_str)
                    self._guides[guide_name] = guide
                except Exception:
                    pass

    async def get_guide(self, app_name: str) -> Optional[AppGuide]:
        """获取操作指南"""
        return self._guides.get(app_name)

    async def save_guide(self, app_name: str, guide: AppGuide) -> bool:
        """保存操作指南"""
        try:
            filepath = os.path.join(self._guides_dir, f"{app_name}.yaml")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(guide.to_yaml())

            self._guides[app_name] = guide
            return True
        except Exception:
            return False

    async def learn_app(self, app_path: str):
        """学习新应用"""
        from .learner import Learner
        learner = Learner()
        return await learner.learn_app(app_path)

    async def list_guides(self) -> List[str]:
        """列出所有操作指南"""
        return list(self._guides.keys())
