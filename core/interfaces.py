"""插件接口定义"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class PluginInterface(ABC):
    """插件基类"""

    name: str
    version: str
    dependencies: List[str]

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化插件"""
        pass

    @abstractmethod
    async def shutdown(self):
        """关闭插件"""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        pass


class GuidePluginInterface(PluginInterface):
    """操作指南插件接口"""

    @abstractmethod
    async def get_guide(self, app_name: str) -> Optional[Dict]:
        """获取操作指南"""
        pass

    @abstractmethod
    async def save_guide(self, app_name: str, guide: Dict) -> bool:
        """保存操作指南"""
        pass

    @abstractmethod
    async def learn_app(self, app_path: str) -> Dict:
        """学习新应用"""
        pass

    @abstractmethod
    async def list_guides(self) -> List[str]:
        """列出所有操作指南"""
        pass


class MousePluginInterface(PluginInterface):
    """鼠标管理插件接口"""

    @abstractmethod
    async def pause(self):
        """暂停 AI 操作"""
        pass

    @abstractmethod
    async def resume(self):
        """继续之前的操作"""
        pass

    @abstractmethod
    async def is_paused(self) -> bool:
        """检查是否暂停"""
        pass


class WaitPluginInterface(PluginInterface):
    """等待工具插件接口"""

    @abstractmethod
    async def wait_for_element(self, target: str, timeout: int = 10) -> bool:
        """等待 UI 元素出现"""
        pass

    @abstractmethod
    async def wait_for_disappear(self, target: str, timeout: int = 10) -> bool:
        """等待 UI 元素消失"""
        pass

    @abstractmethod
    async def wait_for_stable(self, timeout: int = 3) -> bool:
        """等待 UI 稳定"""
        pass
