"""等待插件实现"""

import asyncio
import time
from typing import Any, Optional
from core.interfaces import WaitPluginInterface


class WaitPlugin(WaitPluginInterface):
    """等待插件"""

    name = "wait"
    version = "1.0.0"
    dependencies = []

    def __init__(self):
        self._paused = False

    async def initialize(self) -> bool:
        return True

    async def shutdown(self):
        pass

    async def get_status(self):
        return {"name": self.name, "version": self.version}

    def _get_uia_tree(self) -> Any:
        """获取 UIA 树（可被测试覆盖）"""
        # 这里会调用 uia_engine 插件
        return {}

    def _find_element(self, target: str) -> bool:
        """查找 UI 元素（可被测试覆盖）"""
        # 这里会调用 uia_engine 插件
        return False

    async def wait_for_element(self, target: str, timeout: int = 10) -> bool:
        """等待 UI 元素出现"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._find_element(target):
                return True
            await asyncio.sleep(0.5)
        return False

    async def wait_for_disappear(self, target: str, timeout: int = 10) -> bool:
        """等待 UI 元素消失"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self._find_element(target):
                return True
            await asyncio.sleep(0.5)
        return False

    async def wait_for_stable(self, timeout: int = 3) -> bool:
        """等待 UI 稳定（无变化）"""
        last_tree = None
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_tree = self._get_uia_tree()
            if last_tree is not None and current_tree == last_tree:
                return True
            last_tree = current_tree
            await asyncio.sleep(0.5)
        return False
